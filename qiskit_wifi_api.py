#!/usr/bin/env python3
import socket
import socketserver
import threading
import time
import uuid
from collections import deque, OrderedDict

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit_aer import Aer
import random

HOST = "0.0.0.0"
PORT = 5000

connected_devices = {}
device_logs = deque(maxlen=200)
lock = threading.Lock()

MAX_CIRCUITS_PER_IP = 5
circuits_by_ip = {}
circuits_lock = threading.Lock()

sim_jobs = {}
ibm_jobs = {}


def get_local_ip():
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


def generate_superposition_qubits_ibm_job(n):
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


def configure_ibm_token(token: str):
    QiskitRuntimeService.save_account(token=token, set_as_default=True, overwrite=True)
    print("IBM Quantum token configured.")


def _get_client_ip(client_address):
    return client_address[0]


def _ensure_ip_bucket(ip):
    if ip not in circuits_by_ip:
        circuits_by_ip[ip] = OrderedDict()


def _get_circuit(ip, circuit_id):
    _ensure_ip_bucket(ip)
    if circuit_id not in circuits_by_ip[ip]:
        raise ValueError("circuit-not-found")
    return circuits_by_ip[ip][circuit_id]


def create_circuit_for_ip(ip, q, c):
    with circuits_lock:
        _ensure_ip_bucket(ip)
        if len(circuits_by_ip[ip]) >= MAX_CIRCUITS_PER_IP:
            old_id, _ = circuits_by_ip[ip].popitem(last=False)
            print(f"[CIRCUIT] Evicted {old_id} for {ip}")
        cid = str(uuid.uuid4())[:8]
        circuits_by_ip[ip][cid] = QuantumCircuit(q, c)
        return cid


def delete_circuit_for_ip(ip, cid):
    with circuits_lock:
        _ensure_ip_bucket(ip)
        if cid not in circuits_by_ip[ip]:
            raise ValueError("circuit-not-found")
        del circuits_by_ip[ip][cid]


def reset_circuit_for_ip(ip, cid):
    with circuits_lock:
        qc = _get_circuit(ip, cid)
        circuits_by_ip[ip][cid] = QuantumCircuit(qc.num_qubits, qc.num_clbits)


def clone_circuit_for_ip(ip, cid):
    with circuits_lock:
        _ensure_ip_bucket(ip)
        if len(circuits_by_ip[ip]) >= MAX_CIRCUITS_PER_IP:
            old_id, _ = circuits_by_ip[ip].popitem(last=False)
            print(f"[CIRCUIT] Evicted {old_id} for {ip}")
        new_id = str(uuid.uuid4())[:8]
        circuits_by_ip[ip][new_id] = circuits_by_ip[ip][cid].copy()
        return new_id


def run_circuit_sim(ip, cid):
    qc = _get_circuit(ip, cid)
    backend = Aer.get_backend("qasm_simulator")
    job = backend.run(qc)
    result = job.result()
    counts = result.get_counts()
    job_id = str(uuid.uuid4())[:8]
    sim_jobs[job_id] = {
        "counts": counts,
        "shots": 1024
    }
    return job_id


def run_circuit_ibm(ip, cid):
    qc = _get_circuit(ip, cid)
    service = QiskitRuntimeService()
    backend = service.least_busy(operational=True, simulator=False)
    qc = transpile(qc, backend)
    sampler = Sampler(backend)
    job = sampler.run([qc])
    ibm_jobs[job.job_id()] = job.job_id()
    return job.job_id()


def get_all_job_ids():
    return {
        "sim": list(sim_jobs.keys()),
        "ibm": list(ibm_jobs.keys())
    }


def get_job_status_ibm(job_id: str) -> str:
    """Retrieve the status of a quantum job using IBM Qiskit Runtime."""
    service = QiskitRuntimeService()
    job = service.job(job_id)
    return str(job.status())


def _is_ibm_account_connected() -> bool:
    """Return True if an IBM Quantum account is currently saved/reachable."""
    try:
        QiskitRuntimeService()
        return True
    except Exception:
        return False


def get_job_result_sim(job_id: str) -> dict:
    if job_id not in sim_jobs:
        raise ValueError("job-not-found")
    return sim_jobs[job_id]["counts"]


def get_job_result_ibm(job_id: str) -> dict:
    service = QiskitRuntimeService()
    job = service.job(job_id)
    result = job.result()
    counts = result[0].data['c'].get_counts()
    return counts


def get_job_result(job_id: str) -> dict:
    if job_id in sim_jobs:
        return get_job_result_sim(job_id)

    # Fall back to IBM if an account is available
    if _is_ibm_account_connected():
        return get_job_result_ibm(job_id)

    raise ValueError("job-not-found")


def get_job_sample(job_id: str) -> list[int]:
    """Draw a single random measurement sample from any job (sim or IBM)."""
    counts = get_job_result(job_id)
    states = list(counts.keys())
    weights = list(counts.values())
    bits = random.choices(states, weights=weights, k=1)[0]
    clean_bits = bits.replace(" ", "")
    return [int(b) for b in clean_bits]


def get_job_probabilities_sim(job_id):
    if job_id not in sim_jobs:
        raise ValueError("job-not-found")

    counts = sim_jobs[job_id]["counts"]
    shots = sum(counts.values())

    return {state: c / shots for state, c in counts.items()}


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

            parts = text.strip().split()
            cmd = parts[0].upper()
            args = parts[1:]
            ip = _get_client_ip(self.client_address)

            try:
                if cmd == "LOGS":
                    out = []
                    for e in device_logs:
                        msg = e["msg"].replace("|", "\\|")
                        out.append(f"{int(e['ts'])}:{msg}")
                    if out:
                        self.send_line(f"{','.join(out)}")
                    else:
                        self.send_line("OK")
                elif cmd == "SUPERPOSITION_SIM":
                    n = int(args[0]) if args[0] else 1
                    res = generate_superposition_qubits_simulated(n)
                    self.send_line(f"[{','.join(map(str, res))}]")

                elif cmd == "SUPERPOSITION_IBM":
                    n = int(args[0]) if args[0] else 1
                    out = generate_superposition_qubits_ibm_job(n)
                    self.send_line(out)

                elif cmd == "JOB_STATUS_IBM":
                    job_id = args[0].strip()
                    if not job_id:
                        self.send_line("ERROR jobid-required")
                    else:
                        status = get_job_status_ibm(job_id)
                        self.send_line(f"{status}")

                elif cmd == "CREATE_CIRCUIT":
                    cid = create_circuit_for_ip(ip, int(args[0]), int(args[1]))
                    self.send_line(f"CIRCUIT_ID:{cid}")

                elif cmd == "DELETE_CIRCUIT":
                    delete_circuit_for_ip(ip, args[0])
                    self.send_line("OK")

                elif cmd == "RESET_CIRCUIT":
                    reset_circuit_for_ip(ip, args[0])
                    self.send_line("OK")

                elif cmd == "CLONE_CIRCUIT":
                    cid = clone_circuit_for_ip(ip, args[0])
                    self.send_line(f"CIRCUIT_ID:{cid}")

                elif cmd == "X":
                    _get_circuit(ip, args[0]).x(int(args[1]))
                    self.send_line("OK")

                elif cmd == "H":
                    _get_circuit(ip, args[0]).h(int(args[1]))
                    self.send_line("OK")

                elif cmd == "Y":
                    _get_circuit(ip, args[0]).y(int(args[1]))
                    self.send_line("OK")

                elif cmd == "Z":
                    _get_circuit(ip, args[0]).z(int(args[1]))
                    self.send_line("OK")

                elif cmd == "RX":
                    _get_circuit(ip, args[0]).rx(float(args[2]), int(args[1]))
                    self.send_line("OK")

                elif cmd == "RY":
                    _get_circuit(ip, args[0]).ry(float(args[2]), int(args[1]))
                    self.send_line("OK")

                elif cmd == "RZ":
                    _get_circuit(ip, args[0]).rz(float(args[2]), int(args[1]))
                    self.send_line("OK")

                elif cmd == "CX":
                    _get_circuit(ip, args[0]).cx(int(args[1]), int(args[2]))
                    self.send_line("OK")

                elif cmd == "CZ":
                    _get_circuit(ip, args[0]).cz(int(args[1]), int(args[2]))
                    self.send_line("OK")

                elif cmd == "SWAP":
                    _get_circuit(ip, args[0]).swap(int(args[1]), int(args[2]))
                    self.send_line("OK")

                elif cmd == "MEASURE":
                    _get_circuit(ip, args[0]).measure(int(args[1]), int(args[2]))
                    self.send_line("OK")

                elif cmd == "MEASURE_ALL":
                    _get_circuit(ip, args[0]).measure_all()
                    self.send_line("OK")

                elif cmd == "RUN_CIRCUIT_SIM":
                    job_id = run_circuit_sim(ip, args[0])
                    self.send_line(f"JOBID:{job_id}")

                elif cmd == "RUN_CIRCUIT_IBM":
                    job_id = run_circuit_ibm(ip, args[0])
                    self.send_line(f"JOBID:{job_id}")

                elif cmd == "GET_JOB_SAMPLE":
                    job_id = args[0].strip()
                    if not job_id:
                        self.send_line("ERROR jobid-required")
                    else:
                        res = get_job_sample(job_id)
                        self.send_line(f"[{','.join(map(str, res))}]")

                elif cmd == "GET_ALL_JOB_IDS":
                    jobs = get_all_job_ids()
                    self.send_line(f"SIM={','.join(jobs['sim'])}|IBM={','.join(jobs['ibm'])}")

                elif cmd == "CONFIGURE_IBM":
                    configure_ibm_token(args[0])
                    self.send_line("OK")

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