#!/usr/bin/env python3
import socket
import socketserver
import threading
import time
from collections import deque

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit_aer import Aer

HOST = "0.0.0.0"
PORT = 5000

connected_devices = {}
device_logs = deque(maxlen=200)
lock = threading.Lock()

def get_local_ip():
    """Return a best-effort LAN IP address for this host (does not send packets)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

def generate_superposition_qubits_simulated(n):
    circuit = QuantumCircuit(n, n)
    circuit.h(range(n))
    circuit.measure(range(n), range(n))
    simulator = Aer.get_backend('qasm_simulator')
    job = simulator.run([circuit])
    result = job.result()
    counts = result.get_counts()
    bits = list(counts.keys())[0]
    return list(map(int, list(bits)))

def start_real_ibm_job(n):
    service = QiskitRuntimeService()
    backend = service.least_busy(operational=True, simulator=False)
    print("Using backend:", backend.name, "with gates:", backend.configuration().basis_gates)

    circuit = QuantumCircuit(n, n)
    circuit.h(range(n))
    circuit.measure(range(n), range(n))
    circuit = transpile(circuit, backend)
    sampler = Sampler(backend)
    job = sampler.run([circuit])
    return f"JOBID:{job.job_id()}"

def get_job_status(job_id: str) -> str:
    """Retrieve the status of a quantum job using IBM Qiskit Runtime."""
    service = QiskitRuntimeService()
    job = service.job(job_id)
    return str(job.status())

def get_job_result(job_id: str) -> list[int]:
    """Retrieve the result of a quantum job using IBM Qiskit Runtime."""
    service = QiskitRuntimeService()
    job = service.job(job_id)
    result = job.result()
    counts = result[0].data['c'].get_counts()
    bits = list(counts.keys())[0]
    return list(map(int, list(bits)))

def configure_ibm_token(token: str):
    QiskitRuntimeService.save_account(token=token, set_as_default=True, overwrite=True)
    print("IBM Quantum token configured.")

class Handler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        with lock:
            connected_devices[self.client_address] = {"connected_at": time.time()}
        print(f"[CONNECT] {self.client_address}")

    def send_line(self, text: str):
        """Ensure trailing newline and log what we send."""
        text = "TCPRESPONSE: " + str(text)

        if not text.endswith("\n"):
            text += "\n"

        print(f"[SEND] {self.client_address}: {text.rstrip()}")
        try:
            self.wfile.write(text.encode("utf-8"))
        except Exception as e:
            print("[WRITE ERROR]", e)

    def handle(self):
        while True:
            line = self.rfile.readline()
            if not line:
                break
            try:
                text = line.decode('utf-8').rstrip('\r\n')
            except Exception:
                self.send_line("ERROR invalid-encoding")
                continue
            if not text:
                continue
            print(f"[REQ] {self.client_address}: {text}")

            parts = text.split(' ', 1)
            cmd = parts[0].upper()
            arg = parts[1] if len(parts) > 1 else ""

            try:
                if cmd == "LOG":
                    if not arg:
                        self.send_line("ERROR message-required")
                    else:
                        device_logs.append({"msg": arg, "from": str(self.client_address), "ts": time.time()})
                        print(f"[DEVICE LOG] {arg}")
                        self.send_line("OK")

                elif cmd == "LOGS":
                    out = []
                    for e in device_logs:
                        msg = e["msg"].replace("|", "\\|")
                        out.append(f"{int(e['ts'])}:{msg}")
                    if out:
                        self.send_line(f"{','.join(out)}")
                    else:
                        self.send_line("OK")

                elif cmd == "MEASURE_SIM":
                    n = int(arg) if arg else 1
                    res = generate_superposition_qubits_simulated(n)
                    self.send_line(f"[{','.join(map(str,res))}]")

                elif cmd == "START_JOB":
                    n = int(arg) if arg else 1
                    res = generate_superposition_qubits_simulated(n)
                    self.send_line(f"[{','.join(map(str,res))}]")

                elif cmd == "START_REAL_JOB":
                    n = int(arg) if arg else 1
                    out = start_real_ibm_job(n)
                    self.send_line(out)

                elif cmd == "CONFIGURE_IBM":
                    token = arg.strip()
                    if not token:
                        self.send_line("ERROR token-required")
                    else:
                        configure_ibm_token(token)
                        self.send_line("OK")

                elif cmd == "JOB_STATUS":
                    job_id = arg.strip()
                    if not job_id:
                        self.send_line("ERROR jobid-required")
                    else:
                        status = get_job_status(job_id)
                        self.send_line(f"{status}")

                elif cmd == "JOB_RESULT":
                    job_id = arg.strip()
                    if not job_id:
                        self.send_line("ERROR jobid-required")
                    else:
                        res = get_job_result(job_id)
                        self.send_line(f"[{','.join(map(str,res))}]")

                elif cmd == "STATUS":
                    self.send_line(f"OK running-devices={len(connected_devices)}")

                elif cmd == "HELP":
                    self.send_line("OK Commands: LOG,LOGS,MEASURE n,START_JOB n,START_REAL_JOB n,CONFIGURE_IBM token,STATUS")

                else:
                    self.send_line("ERROR unknown-command")

            except Exception as e:
                self.send_line("ERROR " + str(e))

    def finish(self):
        super().finish()
        with lock:
            if self.client_address in connected_devices:
                del connected_devices[self.client_address]
        print(f"[DISCONNECT] {self.client_address}")

class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 60)
    print("Starting plain-text TCP server")
    print(f"Listening on {local_ip}:{PORT} (binds to {HOST}:{PORT})")
    print("Use this IP in your ESP AT+CIPSTART command, e.g.:")
    print(f'  AT+CIPSTART="TCP","{local_ip}",{PORT}')
    print("=" * 60)

    with ThreadedServer((HOST, PORT), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down")
            server.shutdown()
            server.server_close()