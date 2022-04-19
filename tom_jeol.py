import socket 

# ruska_host = 
# ruska_port = 

tom = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tom.bind((ruska_host, ruska_port))
tom.listen(5)
ongoing = True

while True:
    conn, addr = tom.accept()
    conn.send(str.encode("RUSKA,CTL,This is Major Tom to Ground Control.\n"))
    from_client = ""
    while True:
        data = conn.recv(4096)
        if data.decode() == "CTL,RUSKA,STOP": break
        if data.decode() == "CTL,RUSKA,TERMINATE":
            ongoing = False
            break
        from_client = data[4:].decode()
        print(from_client)
        eval(from_client)
        conn.send(str.encode("RUSKA,CTL,Evaluated Command: "+ from_client +"\n"))
    conn.close()
    print("Client disconnected")
    
tom.close()