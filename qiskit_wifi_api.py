import json
import time
from flask import Flask, request, jsonify
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit_aer import Aer
from collections import deque


app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Store connected devices and their states
connected_devices = {}


def configure_ibm_token(token: str) -> dict:
    """Configure IBM Quantum token"""
    try:
        QiskitRuntimeService.save_account(token=token, channel='ibm_quantum', overwrite=True)
        print("IBM Quantum token configured.")
        return {"status": "success", "message": "IBM token configured"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_superposition_qubits_simulated(num_qubits: int) -> list[int]:
    """Generate superposition qubits using Qiskit Aer simulator"""
    circuit = QuantumCircuit(num_qubits, num_qubits)
    circuit.h(range(num_qubits))
    circuit.measure(range(num_qubits), range(num_qubits))

    simulator = Aer.get_backend('qasm_simulator')
    job = simulator.run([circuit])
    result = job.result()
    counts = result.get_counts()

    return list(map(int, list(counts.keys())[0]))


def start_real_ibm_job(num_qubits: int) -> dict:
    """Start a job on a real IBM Quantum computer and return the job ID"""
    try:
        service = QiskitRuntimeService()
        backend = service.least_busy(operational=True, simulator=False)
        print("Using backend:", backend.name, "with gates:", backend.configuration().basis_gates)

        circuit = QuantumCircuit(num_qubits, num_qubits)
        circuit.h(range(num_qubits))
        circuit.measure(range(num_qubits), range(num_qubits))

        circuit = transpile(circuit, backend)

        sampler = Sampler(backend)
        job = sampler.run([circuit])
        return {"status": "success", "job_id": job.job_id()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_job_status(job_id: str) -> dict:
    """Retrieve the status of a quantum job"""
    try:
        service = QiskitRuntimeService()
        job = service.job(job_id)
        return {"status": "success", "job_status": str(job.status())}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_job_result(job_id: str) -> dict:
    """Retrieve the result of a quantum job"""
    try:
        service = QiskitRuntimeService()
        job = service.job(job_id)
        result = job.result()
        counts = result[0].data['c'].get_counts()

        return {"status": "success", "job_result": list(map(int, list(counts.keys())[0]))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def make_json_response(data, status=200):
    """Helper to create compact JSON response"""
    return app.response_class(
        response=json.dumps(data, separators=(',', ':')),
        status=status,
        mimetype='application/json'
    )


# ============= ENDPOINTS =============

device_logs = deque(maxlen=200)

@app.route('/log', methods=['GET', 'POST'])
def log_msg():
    # Accept ?m=... on GET or JSON {"m": "..."} on POST
    msg = request.args.get('m')
    if msg is None:
        try:
            data = request.get_json(force=True, silent=True) or {}
            msg = data.get('m')
        except Exception:
            msg = None
    if not msg:
        return jsonify({"status": "error", "message": "m is required"}), 400

    entry = {"msg": msg}
    device_logs.append(entry)
    print(f"[DEVICE LOG] {msg}")
    return jsonify({"status": "ok"})

@app.route('/logs', methods=['GET'])
def logs():
    # Return recent logs
    return jsonify({"logs": list(device_logs)})

@app.route('/measure', methods=['GET'])
def measure():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"MEASURE REQUEST from {client_ip}")
    print(f"   Parameters: qbits={request.args.get('qbits', 1)}")

    try:
        num_qubits = int(request.args.get('qbits', 1))
        result = generate_superposition_qubits_simulated(num_qubits)

        # Simple string response
        response_text = "Response:[" + ",".join(map(str, result)) + "]"

        print(f"SENDING RESPONSE:")
        print(f"   {response_text}")
        print(f"{'=' * 60}\n")

        return response_text, 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        error_response = f"Error:{str(e)}"
        print(f"ERROR: {error_response}")
        print(f"{'=' * 60}\n")
        return error_response, 400, {'Content-Type': 'text/plain'}


@app.route('/start_job', methods=['POST', 'GET'])
def start_job():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"START JOB REQUEST from {client_ip}")

    try:
        if request.method == 'POST':
            data = request.get_json()
            num_qubits = data.get('num_qubits', 1)
            print(f"   Method: POST, Body: {data}")
        else:
            num_qubits = int(request.args.get('num_qubits', 1))
            print(f"   Method: GET, Parameters: num_qubits={num_qubits}")

        result = generate_superposition_qubits_simulated(num_qubits)

        response = {'status': 'success', 'job_result': result}

        print(f"SENDING RESPONSE:")
        print(f"   {json.dumps(response, indent=2)}")
        print(f"{'=' * 60}\n")

        return make_json_response(response)
    except Exception as e:
        error_response = {'status': 'error', 'message': str(e)}
        print(f"ERROR: {error_response}")
        print(f"{'=' * 60}\n")
        return make_json_response(error_response, 400)


@app.route('/start_real_job', methods=['POST', 'GET'])
def start_real_job():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"START REAL IBM JOB REQUEST from {client_ip}")

    try:
        if request.method == 'POST':
            data = request.get_json()
            num_qubits = data.get('num_qubits', 1)
        else:
            num_qubits = int(request.args.get('num_qubits', 1))

        result = start_real_ibm_job(num_qubits)

        print(f"SENDING RESPONSE:")
        print(f"   {json.dumps(result, indent=2)}")
        print(f"{'=' * 60}\n")

        return make_json_response(result)
    except Exception as e:
        error_response = {'status': 'error', 'message': str(e)}
        print(f"ERROR: {error_response}")
        return make_json_response(error_response, 400)


@app.route('/configure_ibm', methods=['POST', 'GET'])
def configure_ibm():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"CONFIGURE IBM TOKEN REQUEST from {client_ip}")

    try:
        if request.method == 'POST':
            data = request.get_json()
            token = data.get('token')
        else:
            token = request.args.get('token')

        if not token:
            return make_json_response({'status': 'error', 'message': 'Token is required'}, 400)

        result = configure_ibm_token(token)

        print(f"SENDING RESPONSE:")
        print(f"   {json.dumps(result, indent=2)}")
        print(f"{'=' * 60}\n")

        return make_json_response(result)
    except Exception as e:
        error_response = {'status': 'error', 'message': str(e)}
        return make_json_response(error_response, 400)


@app.route('/job_status', methods=['GET', 'POST'])
def job_status():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"JOB STATUS REQUEST from {client_ip}")

    try:
        if request.method == 'POST':
            data = request.get_json()
            job_id = data.get('job_id')
        else:
            job_id = request.args.get('job_id')

        if not job_id:
            return make_json_response({'status': 'error', 'message': 'job_id is required'}, 400)

        result = get_job_status(job_id)

        print(f"SENDING RESPONSE:")
        print(f"   {json.dumps(result, indent=2)}")
        print(f"{'=' * 60}\n")

        return make_json_response(result)
    except Exception as e:
        error_response = {'status': 'error', 'message': str(e)}
        return make_json_response(error_response, 400)


@app.route('/job_result', methods=['GET', 'POST'])
def job_result():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"JOB RESULT REQUEST from {client_ip}")

    try:
        if request.method == 'POST':
            data = request.get_json()
            job_id = data.get('job_id')
        else:
            job_id = request.args.get('job_id')

        if not job_id:
            return make_json_response({'status': 'error', 'message': 'job_id is required'}, 400)

        result = get_job_result(job_id)

        print(f"SENDING RESPONSE:")
        print(f"   {json.dumps(result, indent=2)}")
        print(f"{'=' * 60}\n")

        return make_json_response(result)
    except Exception as e:
        error_response = {'status': 'error', 'message': str(e)}
        return make_json_response(error_response, 400)


@app.route('/status', methods=['GET'])
def status():
    client_ip = request.remote_addr
    print(f"\n{'=' * 60}")
    print(f"STATUS CHECK from {client_ip}")

    response = {
        'status': 'running',
        'devices': len(connected_devices),
        'endpoints': [
            '/log',
            '/measure',
            '/start_job',
            '/start_real_job',
            '/configure_ibm',
            '/job_status',
            '/job_result',
            '/status'
        ]
    }

    print(f"SENDING RESPONSE:")
    print(f"   {json.dumps(response, indent=2)}")
    print(f"{'=' * 60}\n")

    return make_json_response(response)


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Calliope Quantum Communication Server")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)