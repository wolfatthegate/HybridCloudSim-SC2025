# hybridjob.py

from .job import Job

class HybridJob(Job):
    def __init__(self,
                 job_id,
                 num_qubits,
                 depth,
                 num_shots,
                 priority,
                 arrival_time,
                 circuit_name=None,
                 gates=None,
                 expected_exec_time=None,
                 noise_model=None,
                 phase = "quantum",
                 max_iterations=3):

        super().__init__(job_id=job_id, arrival_time=arrival_time, priority=priority)

        # Quantum parameters
        self.job_id = job_id
        self.circuit_name = circuit_name
        self.num_qubits = num_qubits
        self.depth = depth
        self.num_shots = num_shots
        self.gates = gates
        self.expected_exec_time = expected_exec_time
        self.priority = priority
        self.noise_model = noise_model
        self.arrival_time = arrival_time
        
        # Hybrid execution state
        self.phase = "quantum"  # or "classical"
        self.iteration = 0
        self.max_iterations = max_iterations

    def __repr__(self):
        return (f"HybridJob(job_id={self.job_id}, "
                f"circuit_name={self.circuit_name}, "
                f"phase={self.phase}, "
                f"iter={self.iteration}/{self.max_iterations}, "
                f"num_qubits={self.num_qubits}, "
                f"depth={self.depth}, "
                f"gates={self.gates}, "
                f"priority={self.priority}, "
                f"noise_model={self.noise_model}, "
                f"num_shots={self.num_shots},"
                f"arrival_time={self.arrival_time:.2f})")
