import sys, datetime, time, os
from _thread import start_new_thread
from socket import *

class Server:
    def __init__(self,port,cacheTimeout):
        self.max_conn = 5
        self.buffer = 4096
        self.port = port
        self.cacheTimeout = cacheTimeout

        if not os.path.exists("cache"):
            os.mkdir("cache")

        try:
            self.proxySocket = socket(AF_INET, SOCK_STREAM)
            self.proxySocket.setsockopt(SOL_SOCKET,SO_REUSEADDR,1)
            self.proxySocket.bind(('', self.port))

        except:
            print(self.timeStamp() + "   Error: Cannot start listening...")
            sys.exit(1)

    def timeStamp(self):
        return "[" + str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')) + "]"

    def listenForConnections(self):
        try:
            self.proxySocket.listen(self.max_conn)
            print(self.timeStamp() + "   Listening...")
            while True:
                try:
                    clientSocket, clientAddress = self.proxySocket.accept()
                    start_new_thread(self.connection_read_request, (clientSocket, clientAddress, self.buffer))
                except Exception as e:
                    print(self.timeStamp() + "  Error: Cannot establish connection..." + str(e))
                    sys.exit(1)
            self.proxySocket.close()

        except KeyboardInterrupt:
            print(self.timeStamp() + "   Interrupting Server.")
            time.sleep(.5)

        finally:
            print(self.timeStamp() + "   Stopping Server...")
            sys.exit()


    def generate_header_lines(self, code, length):
        h = ''
        if code == 200:
            h = 'HTTP/1.1 200 OK\n'
            h += 'Server: Proxy\n'

        elif code == 404:
            h = 'HTTP/1.1 404 Not Found\n'
            h += 'Server: Proxy\n'

        h += 'Content-Length: ' + str(length) + '\n'
        h += 'Connection: close\n\n'

        return h

    def connection_read_request(self, conn, addr, buffer):
        try:
            request = conn.recv(buffer)
            header = request.split(b'\n')[0]
            requested_file = request
            requested_file = requested_file.split(b' ')
            url = header.split(b' ')[1]

            hostIndex = url.find(b"://")
            if hostIndex == -1:
                temp = url
            else:
                temp = url[(hostIndex + 3):]

            portIndex = temp.find(b":")

            serverIndex = temp.find(b"/")
            if serverIndex == -1:
                serverIndex = len(temp)

            webserver = ""
            port = -1
            if (portIndex == -1 or serverIndex < portIndex):
                port = 80
                webserver = temp[:serverIndex]
            else:
                port = int((temp[portIndex + 1:])[:serverIndex - portIndex - 1])
                webserver = temp[:portIndex]

            requested_file = requested_file[1]
            print("Requested File ", requested_file)

            method = request.split(b" ")[0]

            # If method is CONNECT it's HTTPS
            if method == b"CONNECT":
                print(self.timeStamp() + "   CONNECT Request")
                self.https_proxy(webserver, port, conn, request, addr, buffer, requested_file)

            # If method is GET it's HTTP
            else:
                print(self.timeStamp() + "   GET Request")
                self.http_proxy(webserver, port, conn, request, addr, buffer, requested_file)

        except Exception as e:
            return

    def http_proxy(self, webserver, port, conn, request, addr, buffer_size, requested_file):
        requested_file = requested_file.replace(b".", b"_").replace(b"http://", b"_").replace(b"/", b"")
        file_path = b"cache/" + requested_file

        isTimeout = False
        if(os.path.exists(file_path)):
            isTimeout = (time.time() - os.path.getctime(file_path)) > self.cacheTimeout

        if os.path.exists(file_path) and not isTimeout:
            print(self.timeStamp() + "  Searching for: ", requested_file)
            print(self.timeStamp() + "  Returning from Cache")

            file_handler = open(b"cache/" + requested_file, 'rb')
            response_content = file_handler.read()
            file_handler.close()
            time.sleep(1)
            conn.send(response_content)
            conn.close()
        else:
            try:
                s = socket(AF_INET, SOCK_STREAM)
                s.connect((webserver, port))
                s.send(request)

                print(self.timeStamp() + "  Forwarding request from ", addr, " to ", webserver)
                file_object = s.makefile('wb', 0)
                file_object.write(b"GET " + b"http://" + requested_file + b" HTTP/1.0\n\n")
                file_object = s.makefile('rb', 0)
                buff = file_object.readlines()
                temp_file = open(b"cache/" + requested_file, "wb+")
                for i in range(0, len(buff)):
                    temp_file.write(buff[i])
                    conn.send(buff[i])

                print(self.timeStamp() + "  Request of client " + str(addr) + " completed...")
                s.close()
                conn.close()

            except Exception as e:
                print(self.timeStamp() + "  Error: forward request..." + str(e))
                return

    def https_proxy(self, webserver, port, conn, request, addr, buffer_size, requested_file):
        requested_file = requested_file.replace(b".", b"_").replace(b"http://", b"_").replace(b"/", b"")

        try:
            print(self.timeStamp() + "  Searching for: ", requested_file)
            file_handler = open(b"cache/" + requested_file, 'rb')
            print("\n")
            print(self.timeStamp() + "  Returning from Cache\n")
            response_content = file_handler.read()
            file_handler.close()
            response_headers = self.generate_header_lines(200, len(response_content))
            conn.send(response_headers.encode("utf-8"))
            time.sleep(1)
            conn.send(response_content)
            conn.close()

        except:
            s = socket(AF_INET, SOCK_STREAM)
            try:
                s.connect((webserver, port))
                reply = "HTTP/1.0 200 Connection established\r\n"
                reply += "Proxy-agent: HTTP\r\n"
                reply += "\r\n"
                conn.sendall(reply.encode())
            except error as err:
                pass

            conn.setblocking(0)
            s.setblocking(0)
            print(self.timeStamp() + "  HTTPS Connection Established")
            while True:
                try:
                    request = conn.recv(buffer_size)
                    s.sendall(request)
                except error as err:
                    pass

                try:
                    reply = s.recv(buffer_size)
                    conn.sendall(reply)
                except error as e:
                    pass

if __name__ == "__main__":
    port = 0
    cacheTimeout = 60
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        if len(sys.argv) > 2:
            cacheTimeout = int(sys.argv[2])
        server = Server(port,cacheTimeout)
        server.listenForConnections()
    else:
        print("Usage: python3 proxy_server.py <port_number> <optional_cache_time_out>")
