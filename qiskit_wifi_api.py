#!/usr/bin/env python3
import socket
import socketserver
import threading
import time
from collections import deque

# (Optional) Qiskit imports reused from your original server.
try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
    from qiskit_aer import Aer
except Exception:
    QuantumCircuit = None
    transpile = None
    QiskitRuntimeService = None
    Sampler = None
    Aer = None

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
    if Aer is None or QuantumCircuit is None:
        # fallback: produce pseudo-random bits if Qiskit not available
        import random
        return [random.randint(0,1) for _ in range(n)]
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
    if QiskitRuntimeService is None:
        return "ERROR qiskit-not-available"
    try:
        service = QiskitRuntimeService()
        backend = service.least_busy(operational=True, simulator=False)
        circuit = QuantumCircuit(n, n)
        circuit.h(range(n))
        circuit.measure(range(n), range(n))
        circuit = transpile(circuit, backend)
        sampler = Sampler(backend)
        job = sampler.run([circuit])
        return f"OK JOBID:{job.job_id()}"
    except Exception as e:
        return "ERROR " + str(e)

class Handler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        with lock:
            connected_devices[self.client_address] = {"connected_at": time.time()}
        print(f"[CONNECT] {self.client_address}")

    def send_line(self, text: str):
        """Log and send a single-line response (ensures trailing newline)."""
        if not text.endswith("\n"):
            out = text + "\n"
        else:
            out = text
        # Print what we're sending so you can see exactly what the Calliope will receive
        print(f"[SEND] {self.client_address}: {out.rstrip()}")
        try:
            self.wfile.write(out.encode('utf-8'))
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
                        self.send_line("ERROR m-required")
                    else:
                        device_logs.append({"msg": arg, "from": str(self.client_address), "ts": time.time()})
                        print(f"[DEVICE LOG] {arg}")
                        self.send_line("OK")

                elif cmd == "LOGS":
                    out = []
                    for e in device_logs:
                        msg = e["msg"].replace("|", "\\|")
                        out.append(f"{int(e['ts'])}:{msg}")
                    self.send_line(",".join(out))

                elif cmd == "MEASURE":
                    n = int(arg) if arg else 1
                    res = generate_superposition_qubits_simulated(n)
                    self.send_line(f"RESPONSE [{','.join(map(str,res))}]")

                elif cmd == "START_JOB":
                    n = int(arg) if arg else 1
                    res = generate_superposition_qubits_simulated(n)
                    self.send_line(f"OK RESULT [{','.join(map(str,res))}]")

                elif cmd == "START_REAL_JOB":
                    n = int(arg) if arg else 1
                    out = start_real_ibm_job(n)
                    self.send_line(out)

                elif cmd == "CONFIGURE_IBM":
                    token = arg.strip()
                    if not token:
                        self.send_line("ERROR token-required")
                    else:
                        # Implement token storage if needed
                        self.send_line("OK token-configured")

                elif cmd == "JOB_STATUS" or cmd == "JOB_RESULT":
                    self.send_line("ERROR not-implemented")

                elif cmd == "STATUS":
                    self.send_line(f"OK running devices={len(connected_devices)}")

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