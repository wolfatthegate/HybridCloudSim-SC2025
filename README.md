# QCloudSim – Hybrid Quantum–HPC Cloud Simulation Framework

QCloudSim is a Python-based simulation framework for modeling, executing, and analyzing hybrid quantum–HPC workloads.  
It enables researchers to evaluate **scheduling strategies**, **resource allocation policies**, and **device utilization trends** in environments that combine noisy Quantum Processing Units (QPUs) with classical High-Performance Computing (HPC) resources such as CPUs and GPUs.

The framework supports:
- **Heterogeneous resources**: QPUs, CPUs, and memory bandwidth modeling.
- **Hybrid workflows**: Alternating quantum and classical computation stages.
- **Custom scheduling**: Parallel, sequential, or user-defined scheduling algorithms.
- **Noise-aware modeling**: Fidelity and noise considerations for realistic QPU behavior.
- **Detailed logging & visualization**: Gantt charts, utilization time series, and average resource usage.

---

## 📦 Features

- **Configurable Devices**
  - Built-in presets for quantum devices (e.g., IBM\_Kawasaki, IBM\_Kyiv).
  - Built-in presets for classical CPUs (e.g., AMD EPYC 9654, NVIDIA Grace Hopper).
  - Adjustable qubit counts, CPU cores, and memory bandwidth capacities.

- **Workload Management**
  - Supports job dispatch from CSV files or generated workloads.
  - Tracks arrival, start, finish times for each device stage.
  - Measures per-resource utilization over time.

- **Visualization Tools**
  - **Gantt Charts** – visualize execution phases across devices.
  - **Utilization Time Series** – track CPU, QPU, and memory bandwidth usage.
  - **Average Utilization Bar Charts** – compare overall resource demands.

---

## 🛠 Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/QCloudSim.git
cd QCloudSim
```


Below is a minimal example of running a hybrid simulation with two QPUs and two CPUs.

```python

from QCloud import *

PRINTLOG = False

# Devices
ibm_kawasaki = IBM_Kawasaki(env=None, name="QPU-1", printlog=PRINTLOG)
ibm_kyiv     = IBM_Kyiv(env=None, name="QPU-2", printlog=PRINTLOG)
cpu1         = CPU("CPU-1", env=None)
cpu2         = CPU("CPU-2", env=None)

# Hybrid environment
sim_env = HybridCloudSimEnv(
    qpu_devices=[ibm_kawasaki, ibm_kyiv],
    cpu_devices=[cpu1, cpu2],
    broker_class=ParallelBroker,
    job_feed_method='dispatcher',
    file_path='synth_job_batches/10-job.csv', 
    job_generation_model=None, 
    printlog=PRINTLOG
)

# Run the simulation
sim_env.run()
```

Repository Structure
```
QCloudSim/
│
├── QCloud/                 # Core framework package
│   ├── devices.py          # Device definitions (QPU, CPU, etc.)
│   ├── dependencies.py     # Presets and constants
│   ├── __init__.py         # Unified imports
│   ├── hybridcloudsimenv.py# Hybrid simulation environment
│   ├── brokers.py          # Scheduling/broker logic
│   └── utils.py            # Utility functions
│
├── synth_job_batches/      # Example job CSV files
├── Images/                 # Example plots
├── requirements.txt        # Python dependencies
└── README.md               # This file
```
