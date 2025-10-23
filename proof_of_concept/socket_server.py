import select
import socket
import yaml

HOST = '127.0.0.1'
PORT = 12345

# One generic device class. Every command is either a Getter or a Setter
class Device:

    def __init__(self, name, port, vars, commands):
        self.name = name
        self.port = port
        self.status_variables = vars
        self.valid_commands = commands

    def get(self, var) -> any:
        if var in self.status_variables:
            v = self.status_variables[var]
            if "value" in v:
                return v["value"]
            else:
                raise Exception(f"Value of {var} not set yet")
        else:
            raise Exception(f"Variable {var} does not exist")
        
    def set(self, var, val) -> any:
        if var not in self.status_variables:
            self.status_variables[var] = {}
        v = self.status_variables[var]
        if val not in v["valid_values"]:
            raise Exception(f"{val} is not a valid value for {var}")
        v["value"] = val
        return v["value"]

    # Check if given command is in the device config
    def isValidCommand(self, command) -> bool:
        for cmd in self.valid_commands:
            if cmd["input"] == command:
                return cmd
        return False

    def __str__(self) -> str:
        return f"{self.name} at port {self.port}"
    
# Read Config File
def read_device_types():
    with open("device_types.yml", "r") as device_types:
        device_config = yaml.safe_load(device_types)
    
    return device_config["device_types"]

# Server Code
if __name__ == "__main__":
    device_types = read_device_types()
    port_registry = {}
    for device in device_types:
        port_registry[device["port"]] = device

    server_sockets = []
    for port in port_registry:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, port))
        server_socket.listen(5)
        server_sockets.append(server_socket)
        print(f"Listening on {HOST}:{port}")

    client_sockets = {}
    while True:

        # Use select to wait until something is ready
        readable, writable, errored = select.select(server_sockets + list(client_sockets.keys()), [], [])

        for s in readable:

            # New Connection
            if s in server_sockets:
                conn, addr = s.accept()
                port = s.getsockname()[1]
                conn.setblocking(False)

                device = port_registry[port]
                client_sockets[conn] = Device(name=device["name"], port=device["port"], vars=device["status_variables"], commands=device["valid_commands"])

                conn.sendall(f"Connected to {device["name"]} on port {port}\r".encode('utf-8'))

            # Existing Connection
            else:
                data = s.recv(1024)

                # Client Connection Closed
                if not data:
                    s.close()
                    del client_sockets[s]

                # Process Client Input
                else:
                    recieved = data.decode().rstrip("\r\n")
                    device = client_sockets[s]
                    if cmd := device.isValidCommand(recieved):
                        if "function" in cmd:
                            process_return = getattr(device, cmd["function"])(*cmd["parameters"])
                            formatting = {var: device.status_variables[var]["value"] for var in device.status_variables}
                        else:
                            formatting = {}
                        output = cmd["output"].format(**formatting)
                        s.sendall(output.encode("utf-8"))
                    else:
                        raise Exception(f"Invalid Command: '{recieved}'")

    

