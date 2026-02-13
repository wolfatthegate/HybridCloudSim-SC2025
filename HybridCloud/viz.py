# viz.py
# Matplotlib-only (no seaborn), works with your job_records_manager.records

import matplotlib.pyplot as plt
import math 
import matplotlib.patches as mpatches
import numpy as np

def _safe_list(row, key):
    v = row.get(key, [])
    return v if isinstance(v, list) else ([] if v is None else [v])

def _iters(row):
    # number of iterations = min of available arrays (defensive)
    n = min(len(_safe_list(row, 'qpu_start')),
            len(_safe_list(row, 'qpu_finish')),
            len(_safe_list(row, 'cpu_start')),
            len(_safe_list(row, 'cpu_finish')))
    return n

def plot_gantt(job_records, DISPLAY, title="Hybrid QPU/CPU Timeline"):
    """
    One horizontal row per job; each iteration shows QPU then CPU spans.
    """
    if not job_records:
        print("No records to plot.")
        return

    jobs = sorted(job_records.keys())
    fig, ax = plt.subplots(figsize=(12, max(3, 0.6*len(jobs))))

    ytick, ylabels = [], []
    colors = {"QPU": "#0496ff", "CPU": "#f25c54"}

    for idx, job_id in enumerate(jobs):
        if job_id > DISPLAY:  # only first 10 jobs
            break

        row = job_records[job_id]
        n = _iters(row)
        qs = _safe_list(row, 'qpu_start')[:n]
        qf = _safe_list(row, 'qpu_finish')[:n]
        cs = _safe_list(row, 'cpu_start')[:n]
        cf = _safe_list(row, 'cpu_finish')[:n]

        # draw spans
        for i in range(n):
            # QPU bar
            ax.barh(idx, qf[i] - qs[i], left=qs[i], height=0.65,
                    edgecolor='black', color=colors["QPU"], alpha=0.9)
            ax.text(qs[i], idx , f" itr#{i}", fontsize=16, va='center', ha='left')

            # CPU bar
            ax.barh(idx, cf[i] - cs[i], left=cs[i], height=0.65,
                    edgecolor='black', color=colors["CPU"], alpha=0.9)
            ax.text(cs[i], idx , f"", fontsize=16, va='center', ha='left')

        ytick.append(idx)
        ylabels.append(f"Job {job_id}")

    ax.set_yticks(ytick)
    ax.set_yticklabels(ylabels, fontsize=20)
    ax.set_xlabel("Sim time", fontsize=20)
    # ax.set_title(title, fontsize=16)
    ax.tick_params(axis='x', labelsize=20)
    ax.grid(axis='x', linestyle=':', alpha=0.4)

    # Add legend
    legend_handles = [
        mpatches.Patch(color=colors["QPU"], label="QPU Phase"),
        mpatches.Patch(color=colors["CPU"], label="CPU Phase")
    ]
    ax.legend(handles=legend_handles, loc='upper right', fontsize=17, frameon=True)

    fig.tight_layout()
    plt.show()

def print_phase_metrics(job_records, DISPLAY):
    """
    Prints wait / service / turnaround per phase & iteration.
    wait   = start - arrive
    svc    = finish - start
    turn   = finish - arrive
    """
    for job_id in sorted(job_records.keys()):
 
        if job_id > DISPLAY: 
            break
        row = job_records[job_id]
        n = _iters(row)
        if n == 0:
            continue

        qa = _safe_list(row, 'qpu_arrive')[:n]
        qs = _safe_list(row, 'qpu_start')[:n]
        qf = _safe_list(row, 'qpu_finish')[:n]
        ca = _safe_list(row, 'cpu_arrive')[:n]
        cs = _safe_list(row, 'cpu_start')[:n]
        cf = _safe_list(row, 'cpu_finish')[:n]
        
        if not True: 
            print(f"\nJob {job_id} (iterations={n}):")
            for i in range(n):
                q_wait = round(qs[i] - qa[i], 4)
                q_svc  = round(qf[i] - qs[i], 4)
                q_turn = round(qf[i] - qa[i], 4)

                c_wait = round(cs[i] - ca[i], 4)
                c_svc  = round(cf[i] - cs[i], 4)
                c_turn = round(cf[i] - ca[i], 4)

                print(f"  iter {i}: "
                      f"QPU[wait={q_wait}, svc={q_svc}, turn={q_turn}]  |  "
                      f"CPU[wait={c_wait}, svc={c_svc}, turn={c_turn}]")


def plot_all(job_records, display):
    print_phase_metrics(job_records, DISPLAY = display)
    plot_gantt(job_records, DISPLAY = display)
    
def calculate_device_usage_units(job_records, sim_env):

    T = sim_env.now
    if T <= 0:
        raise ValueError("Simulation time is zero.")

    # Capacities
    qpu_units_cap = sum(getattr(d, "container", None).capacity for d in getattr(sim_env, "qpu_devices", []) if getattr(d, "container", None))
    cpu_units_cap = sum(getattr(d, "container", None).capacity for d in getattr(sim_env, "cpu_devices", []) if getattr(d, "container", None))
    mem_bw_cap    = sum(getattr(d, "mem_bw",    None).capacity for d in getattr(sim_env, "cpu_devices", []) if getattr(d, "mem_bw", None))

    qpu_units_time = 0.0
    cpu_units_time = 0.0
    mem_bw_time    = 0.0

    for _, rec in job_records.items():
        qs = rec.get('qpu_start', []) or []
        qf = rec.get('qpu_finish', []) or []
        qu = rec.get('qpu_units', []) or []  # if you logged it; otherwise assume 1

        cs = rec.get('cpu_start', []) or []
        cf = rec.get('cpu_finish', []) or []
        cu = rec.get('cpu_units', []) or []
        mb = rec.get('cpu_mem_bw', []) or []

        n_q = min(len(qs), len(qf), len(qu)) if qu else min(len(qs), len(qf))
        n_c = min(len(cs), len(cf), len(cu), len(mb)) if (cu and mb) else min(len(cs), len(cf))

        # QPU: treat each phase weight by qubits (if available) else 1
        for i in range(n_q):
            s, f = qs[i], qf[i]
            units = (qu[i] if qu else 1)
            if s is not None and f is not None and f >= s:
                qpu_units_time += (f - s) * units

        # CPU: accumulate BOTH CPU-units*time and mem-bw*time
        for i in range(n_c):
            s, f = cs[i], cf[i]
            cpu_units = (cu[i] if cu else 1)
            mem_units = (mb[i] if mb else 1)
            if s is not None and f is not None and f >= s:
                dt = (f - s)
                cpu_units_time += dt * cpu_units
                mem_bw_time    += dt * mem_units

    # Denominators
    qpu_den = max(1e-12, qpu_units_cap * T) if qpu_units_cap else 1e-12
    cpu_den = max(1e-12, cpu_units_cap * T) if cpu_units_cap else 1e-12
    mbw_den = max(1e-12, mem_bw_cap    * T) if mem_bw_cap    else 1e-12

    return {
        "time": round(T, 2),
        "qpu_util_percent": round(100.0 * qpu_units_time / qpu_den, 2) if qpu_units_cap else 0.0,
        "cpu_util_percent": round(100.0 * cpu_units_time / cpu_den, 2) if cpu_units_cap else 0.0,
        "mem_bw_util_percent": round(100.0 * mem_bw_time / mbw_den, 2) if mem_bw_cap else 0.0,
        "qpu_units_time": round(qpu_units_time, 2),
        "cpu_units_time": round(cpu_units_time, 2),
        "mem_bw_time": round(mem_bw_time, 2),
        "qpu_units_capacity": qpu_units_cap,
        "cpu_units_capacity": cpu_units_cap,
        "mem_bw_capacity": mem_bw_cap,
    }

def plot_cpu_resource_util(util):
    labels = ["CPU units", "Memory BW"]
    vals = [util["cpu_util_percent"], util["mem_bw_util_percent"]]
    fig, ax = plt.subplots(figsize=(6,4))
    ax.bar(labels, vals)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Utilization (%)", fontsize=12)
    ax.set_title("CPU Resource Utilization", fontsize=14)
    for i, v in enumerate(vals):
        ax.text(i, v + 2, f"{v:.2f}%", ha="center", va="bottom", fontsize=12)
    fig.tight_layout()
    plt.show()
    
def plot_processors_utilization(util):
    labels = ["QPU", "CPU"]
    values = [util["qpu_utilization_percent"], util["cpu_utilization_percent"]]
    fig, ax = plt.subplots(figsize=(6,4))
    ax.bar(labels, values)
    # ax.set_ylim(0, 100)
    ax.set_ylabel("Usage (%)", fontsize=12)
    # ax.set_title("Device Utilization", fontsize=14)
    ax.tick_params(axis='both', labelsize=12)
    for i, v in enumerate(values):
        ax.text(i, v - 1, f"{v:.2f}%", ha="center", va="bottom", fontsize=12)
    fig.tight_layout()
    plt.show()
    
def plot_hybrid_utilization(util):
    """
    Draw one bar chart showing QPU, CPU-unit, and Memory-BW utilization (%).
    """
    # accept either naming style
    qpu = util.get("qpu_utilization_percent", util.get("qpu_util_percent", 0.0))
    cpu = util.get("cpu_utilization_percent", util.get("cpu_util_percent", 0.0))
    mbw = util.get("mem_bw_util_percent", 0.0)

    # ensure numeric floats
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    qpu = _to_float(qpu)
    cpu = _to_float(cpu)
    mbw = _to_float(mbw)

    # clamp to [0, 100]
    vals = [max(0.0, min(100.0, v)) for v in [qpu, cpu, mbw]]
    labels = ["QPU", "CPU units", "Memory\nBandwidth"]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))

    # pick custom colors & outline
    colors = ["#0496ff", "#f25c54", "#9c27b0"]
    bars = ax.bar(labels, vals, color=colors, edgecolor="black", linewidth=1.2)

    # make ticks larger
    ax.tick_params(axis='x', labelsize=18)  # X-ticks fontsize

    ax.set_ylabel("Usage (%)", fontsize=20)
    ax.tick_params(axis='y', labelsize=16)  # y-axis tick labels
    ax.grid(axis='y', linestyle=':', alpha=0.35)

    # annotate each bar
    for rect, v in zip(bars, vals):
        ax.text(rect.get_x() + rect.get_width() / 2.0,
                v,
                f"{v:.2f}%",
                ha="center", va="bottom", fontsize=17)
    plt.ylim(0, 100)
    fig.tight_layout()
    plt.show()
    

def utilization_time_series(job_records, 
                                  qpu_capacity_units,   # e.g., sum of QPU container.capacity across devices
                                  cpu_capacity_units,   # e.g., sum of CPU container.capacity across devices
                                  mem_bw_capacity_units,# e.g., sum of CPU mem_bw.capacity across devices
                                  step=0.5):
    """
    Capacity-aware utilization over time:
      QPU: sum of qubits-in-use / total QPU qubits
      CPU: sum of cpu_units-in-use / total CPU units
      MemBW: sum of mem_bw-in-use / total MemBW units
    """

    # 1) Determine total simulation horizon from last finish
    max_t = 0.0
    for rec in job_records.values():
        if rec.get("qpu_finish"):
            max_t = max(max_t, max(rec["qpu_finish"]))
        if rec.get("cpu_finish"):
            max_t = max(max_t, max(rec["cpu_finish"]))
    if max_t <= 0:
        return np.array([0.0]), [0.0], [0.0], [0.0]

    ts = np.arange(0.0, max_t + step, step)

    qpu_util = []
    cpu_util = []
    mbw_util = []

    # 2) Sample each timestamp
    for t in ts:
        qpu_busy_units = 0
        cpu_busy_units = 0
        mem_busy_units = 0

        for rec in job_records.values():
            # QPU: add qubits for each active QPU slice
            q_s = rec.get("qpu_start", []) or []
            q_f = rec.get("qpu_finish", []) or []
            q_u = rec.get("qpu_units", []) or []
            n_q = min(len(q_s), len(q_f), len(q_u))
            for i in range(n_q):
                s, f, u = q_s[i], q_f[i], int(q_u[i])
                if s <= t < f:
                    qpu_busy_units += u

            # CPU: add cpu_units and mem_bw for each active CPU slice
            c_s = rec.get("cpu_start", []) or []
            c_f = rec.get("cpu_finish", []) or []
            c_u = rec.get("cpu_units", []) or []
            c_b = rec.get("cpu_mem_bw", []) or []
            n_c = min(len(c_s), len(c_f), len(c_u), len(c_b))
            for i in range(n_c):
                s, f = c_s[i], c_f[i]
                u = int(c_u[i])
                bw = int(c_b[i])
                if s <= t < f:
                    cpu_busy_units += u
                    mem_busy_units += bw

        # 3) Convert to percentages against capacities
        qpu_pct = 100.0 * qpu_busy_units / max(1e-12, qpu_capacity_units)
        cpu_pct = 100.0 * cpu_busy_units / max(1e-12, cpu_capacity_units)
        mbw_pct = 100.0 * mem_busy_units / max(1e-12, mem_bw_capacity_units)

        # Clamp for display
        qpu_util.append(max(0.0, min(100.0, qpu_pct)))
        cpu_util.append(max(0.0, min(100.0, cpu_pct)))
        mbw_util.append(max(0.0, min(100.0, mbw_pct)))

    return ts, qpu_util, cpu_util, mbw_util

def plot_utilization_over_time(time_points, qpu_util, cpu_util, mem_util):
    plt.figure(figsize=(10, 5))
    plt.plot(time_points, qpu_util, label="QPU Utilization", color="#0496ff")
    plt.plot(time_points, cpu_util, label="CPU Utilization", color="#f25c54")
    plt.plot(time_points, mem_util, label="MemBW Utilization", color="#9c27b0")
    plt.xlabel("Simulation Time", fontsize=20)
    plt.ylabel("Utilization (%)", fontsize=20)
    # plt.title("Resource Utilization Over Time")
    # plt.ylim(0, 110)
    plt.grid(True, linestyle=":")
    plt.legend(fontsize=14)
    plt.tight_layout()
    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    plt.show()