from PyJEM import TEM3, detector
import json
import toml
import datetime
from time import sleep
from math import tan, acos, sqrt, pi
# import h5py

class PtychoMode():
    
    def __init__(self, calibration=None):
        # Used in methods
        self.eos = TEM3.EOS3()
        self.apt = TEM3.Apt3()
        self.lens = TEM3.Lens3()
        self.feg = TEM3.FEG3()
        self.defl = TEM3.Def3()
        self.det = TEM3.Detector3()
        self.detector = detector
        self.ht = TEM3.HT3()
        self.adf1 = detector.Detector(0)

        # Used only for getting parameters
        self.gun = TEM3.GUN3()
        self.stage = TEM3.Stage3()
        self.scan = TEM3.Scan3()

        self.calibration = calibration
        self.zero_defocus = 0 # nm
        self.defocus = 0 # nm

    def std_focus(self):
        # TODO: Add value range check, [0, 65535]
        self.lens.SetOLc(63270) #F726
        self.lens.SetOLf(32774) #8006
        self.lens.SetOLSuperFineSw(1)
        self.lens.SetOLSuperFineValue(2048) #0800
        self.lens.SetOLSuperFineSw(0)
        # Reset the displayed defocus
        max_mag = 150000000
        if self.eos.GetMagValue()[0] == max_mag:
            self.eos.DownSelector()        
            self.eos.UpSelector()
        else:                
            self.eos.UpSelector()
            self.eos.DownSelector()

    def change_defocus(self, defocus):
        self.lens.SetOLSuperFineSw(0)
        # This needs to be calibrated for OLc, OLf, OLsf independently, although usually on OLf is used.
        # TODO: calibration defocus_per_bit(nm) for all kVs and use dict()
        # At 300kV, OLf 1 bit -> 4.520 nm
            # ht = str(self.ht.GetHtValue())
            # defocus_per_bit = self.calibration['defocus_per_bit'][ht]
        defocus_per_bit = 4.520
        self.eos.SetObjFocus(int(defocus/defocus_per_bit))

    # aquisition_focus - std_focus = defocus + zero_defocus
    # aquisition_focus                                  std_focus 
    #        |<-------------------------->|<-------------->|
    #                    defocus             zero_defocus
    def set_acquisition_focus__nm(self, defocus):
        self.defocus = defocus
        self.std_focus()
        self.change_defocus(defocus + self.zero_defocus)

    def set_acquisition_focus__um(self, defocus):
        self.set_acquisition_focus__nm(self, defocus * 1000)

    def set_array_size(self, array_size):
        size_list = [64, 128, 256, 512, 1024, 2048, 3072, 4096]
        # Find the nearest size accepted by JOEL Scan
        difference = lambda list : abs(list - array_size)
        input_array_size = min(size_list, key=difference)
        self.adf1.set_imaging_area(Width=array_size, Height=input_array_size)

    # TODO: Merge in to params collection
    def get_cl_aperture(self):
        self.cl_aperture1 = self.apt.GetExpSize(0)
        self.cl_aperture2 = self.apt.GetExpSize(1)

    def set_cl_aperture(self, type, size):
        type_dict = {'CLApt1': 0, 'CLApt2': 1}
        self.apt.SetExpSize(type_dict[type], size)
        if type == 'CLApt1':
            self.apt.SetExpSize(type_dict['CLApt2'], 0)
        if type == 'CLApt2':
            self.apt.SetExpSize(type_dict['CLApt1'], 0)

    def open_beam_valve(self):
        self.feg.SetBeamValve(1)
        
    def close_beam_valve(self):
        self.feg.SetBeamValve(0)
        
    # This could be done with Ronchigram mode if it doesn't interfere with the scan
    # TODO: "Check before clear" may reduce the time needed
    def clear_detector_channels(self):
        for i in range(4):
            self.detector.assign_channel('None', i)
            sleep(1)

    def beam_blanking(self, on_off):
        self.defl.SetBeamBlank(on_off)

    # SetScreen didn't work initially for some reason.
    def screen_down(self):
        self.det.SetScreen(0)

    def focus_screen(self):
        self.det.SetScreen(1)

    def screen_up(self):
        self.det.SetScreen(2)

    def set_dwell_time_us(self, dwell_time):
        self.adf1.set_exposuretime_value(dwell_time)      
        
    def set_magnification(self, mag):
        current_mag = self.eos.GetMagValue()[0]
        diff = abs(current_mag - mag)
        if current_mag == mag:
            return
        elif current_mag > mag:
            self.eos.DownSelector()
        else:
            self.eos.UpSelector()
        new_mag = self.eos.GetMagValue()[0]
        if new_mag == mag:
            return
        new_diff = abs(new_mag - mag)
        if (new_mag - mag) * (current_mag - mag) > 0:
            self.set_magnification(mag)
        elif new_diff > diff:
            self.set_magnification(mag)
        return

    # TODO: Read step size calibration from config dict
    def get_step_size(self):
        step_size_250K_128 = 3.12 # nm
        array_size = self.adf1.get_detectorsetting()['ImagingArea']['Height']
        mag = self.eos.GetMagValue()[0]
        return step_size_250K_128 * 250000/mag * 128/array_size
    
    def get_probe_radius(self):
        alpha = self.get_convergence()
        l = self.get_merlin_camera_length()
        return tan(alpha) * l

    def circular_probe_overlap(self):
        r = self.get_probe_radius()
        d = self.get_step_size()
        # https://mathworld.wolfram.com/Circle-CircleIntersection.html
        overlap_area = 2 * r**2 * acos(d/(2*r)) - 0.5 * d * sqrt(4 * r**2 - d**2)
        circle_area = pi * r**2
        overlap_pct = overlap_area / circle_area * 100
        return [overlap_area, overlap_pct] 
        
    # `instrument` metadata is collected at acquisition time;
    # `calibration` metadata is from input and should stay unchanged;
    # `calculation` metadata is calucated at acquisition time after `instument` metadata is collected;
    # `instrument` metadata is collected at acquisition time, but related to user input.
    def collect_metadata(self, print_to_screen=True):
        instrument = {
            'HT(kV)': self.ht.GetHtValue() / 1000,
            'A1(kV)': self.gun.GetAnode1CurrentValue(),
            'A2(kV)': self.gun.GetAnode2CurrentValue(),
            'CLApt1' : self.apt.GetExpSize(0),
            'CLApt2' : self.apt.GetExpSize(1),
            'SpotSize': self.eos.GetSpotSize(),
            'NominalCameraLength(m)': self.eos.GetStemCamValue(),
            'Magnification': self.eos.GetMagValue()[0],
            'ArraySize': self.adf1.get_detectorsetting()['ImagingArea']['Height'],
            'NominalScanRotation': self.scan.GetRotationAngle(),
            'PosX(m)': self.stage.GetPos()[0] * 10**-9,
            'PosY(m)': self.stage.GetPos()[1] * 10**-9,
            'PosZ(m)': self.stage.GetPos()[2] * 10**-9,
            'TiltX(deg)': self.stage.GetPos()[3],
            'TiltY(deg)': self.stage.GetPos()[4],
            'CL1': self.lens.GetCL1(),
            'CL2': self.lens.GetCL2(),
            'CL3': self.lens.GetCL3(),
            'CM': self.lens.GetCM(),
            'IL1': self.lens.GetIL1(),
            'IL2': self.lens.GetIL2(),
            'IL3': self.lens.GetIL3(),
            'OLSF': self.lens.GetOLSuperFineValue(),
            'OLC': self.lens.GetOLc(),
            'OLF': self.lens.GetOLf(),
            'OM': self.lens.GetOM(),
            'PL1': self.lens.GetPL1(),
            'CLA1': self.defl.GetCLA1(),
            'CLA2': self.defl.GetCLA2(),
            'CLS': self.defl.GetCLs(),
            'Correction': self.defl.GetCorrection(),
            'GUNA1': self.defl.GetGunA1(),
            'GUNA2': self.defl.GetGunA2(),
            'ILS': self.defl.GetILs(),
            'IS1': self.defl.GetIS1(),
            'IS2': self.defl.GetIS2(),
            'MAGADJUST': self.defl.GetMagAdjust(),
            'OLS': self.defl.GetOLs(),
            'OFFSET': self.defl.GetOffset(),
            'PLA': self.defl.GetPLA(),
            'ROTATION': self.defl.GetRotation(),
            'SCAN1': self.defl.GetScan1(),
            'SCAN2': self.defl.GetScan2(),
            'SHIFBAL': self.defl.GetShifBal(),
            'SPOTA': self.defl.GetSpotA(),
            'STEMIS': self.defl.GetStemIS(),
            'TILTBAL': self.defl.GetTiltBal(),
            'ANGBAL': self.defl.GetAngBal()
            }

        # TODO: Include clock synchronisation in the `calibration` or `calcuation` dict
        # 'tempc_clock_offset': 0
        # 'merlinpc_clock_offset': 0
        calibration = self.calibration

        calculation = {
            'merlin_camera_length(m)': self.get_merlin_camera_length(),
            'convergence_semi-angle(rad)': self.get_convergence(),
            'probe_radius(nm)': self.get_probe_radius(),
            'step_size(nm)': self.get_step_size(),
            'overlap(nm^2)': self.circular_probe_overlap()[0],
            'overlap_ratio(%)': self.circular_probe_overlap()[1],
            'field_of_view(m)': self.get_step_size() * instrument['ArraySize'],
            }

        acquisition = {
            'zero_defocus(nm)': self.zero_defocus,
            'defocus(nm)': self.defocus,
            'time_stamp': datetime.datetime.now(),
            'file_dir': "",
            'file_path': "",
            'file_prefix': "",
            }

        self.metadata = {'instrument': instrument, 'calibration': calibration, 'calculation': calculation, 'acquisition': acquisition}
        self.print_metadata()

    # TODO: Check if all the Set functions are available
    def restore_lens_values(self, instrument_dict):
        self.lens.GetCL1(instrument_dict['CL1'])
        self.lens.GetCL2(instrument_dict['CL2'])
        self.lens.GetCL3(instrument_dict['CL3'])
        self.lens.GetCM(instrument_dict['CM'])
        self.lens.GetIL1(instrument_dict['IL1'])
        self.lens.GetIL2(instrument_dict['IL2'])
        self.lens.GetIL3(instrument_dict['IL3'])
        self.lens.GetOLSuperFineValue(instrument_dict['OLSF'])
        self.lens.GetOLc(instrument_dict['OLC'])
        self.lens.GetOLf(instrument_dict['OLF'])
        self.lens.GetOM(instrument_dict['OM'])
        self.lens.GetPL1(instrument_dict['PL1'])

    # TODO: Check if all the Set functions are available
    # TODO: Use Get methods to compare value first before change? (maybe)
    def restore_deflector_values(self, instrument_dict):
        self.defl.SetCLA1(instrument_dict['CLA1'])
        self.defl.SetCLA2(instrument_dict['CLA2'])
        self.defl.SetCLs(instrument_dict['CLS'])
        self.defl.SetCorrection(instrument_dict['Correction'])
        self.defl.SetGunA1(instrument_dict['GUNA1'])
        self.defl.SetGunA2(instrument_dict['GUNA2'])
        self.defl.SetILs(instrument_dict['ILS'])
        self.defl.SetIS1(instrument_dict['IS1'])
        self.defl.SetIS2(instrument_dict['IS2'])
        self.defl.SetMagAdjust(instrument_dict['MAGADJUST'])
        self.defl.SetOLs(instrument_dict['OLS'])
        self.defl.SetOffset(instrument_dict['OFFSET'])
        self.defl.SetPLA(instrument_dict['PLA'])
        self.defl.SetRotation(instrument_dict['ROTATION'])
        self.defl.SetScan1(instrument_dict['SCAN1'])
        self.defl.SetScan2(instrument_dict['SCAN2'])
        self.defl.SetShifBal(instrument_dict['SHIFBAL'])
        self.defl.SetSpotA(instrument_dict['SPOTA'])
        self.defl.SetStemIS(instrument_dict['STEMIS'])
        self.defl.SetTiltBal(instrument_dict['TILTBAL'])
        self.defl.SetAngBal(instrument_dict['ANGBAL'])

    # TODO: calibration convergence semi-angle and use dict()
    # TODO: this needs to go into an input file
    def get_convergence(self):
        ht = str(self.ht.GetHtValue())
        clapt1_list = [1000, 150, 100, 70, 10]
        clapt2_list = [1000, 50, 40, 30, 20]
        clapt1_idx = self.apt.GetExpSize(0)
        clapt2_idx = self.apt.GetExpSize(1)

        if clapt1_idx == 0 and clapt2_idx == 0:
            # No aperture. Will this cause problem for reconstruction?
            convergence = 1000
        else:
            if clapt1_list[clapt1_idx] > clapt2_list[clapt2_idx]:
                convergence = self.calibration['convergence_semi-angle'][ht]['CLApt2'][str(clapt2_idx)]
            else:
                convergence = self.calibration['convergence_semi-angle'][ht]['CLApt1'][str(clapt1_idx)]
        return convergence

    def get_merlin_camera_length(self):
        return

    # TODO: Add default file path
    # TODO: Include `file_path` and `file_dir` in the metadata
    def metadata_to_toml(self, filename):
        self.collect_metadata()
        with open(filename, 'a') as f:
            f.write(toml.dumps(self.metadata))

    def metadata_to_json(self, filename):
        self.collect_metadata()
        with open(filename, 'a') as f:
            f.write(json.dumps(self.metadata), indent=4)

    # TODO: Decide on file format (compatability with ePSIC, etc.)
    # def write_hdf(self, filename):
    #     with h5py.File(filename,'w') as f:
    #         data_group = f.create_group('experiment:NXentry/data:NXdata')
    #         data_group['data'] = h5py.ExternalLink(filename[:-3]+"_data.hdf", "/Experiments/__unamed__/data")

    def print_metadata(self, format='toml'):
        if format == 'toml':
            print(toml.dumps(self.metadata))
        elif format == 'json':
            print(toml.dumps(self.metadata))
        else:
            print("Unknow format: ", format, ". Please choose toml or json.")

if __name__ == '__main__':
    ruska = PtychoMode()
