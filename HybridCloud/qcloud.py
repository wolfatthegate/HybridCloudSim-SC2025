# qcloud.py

from HybridCloud.dependencies import *
import numpy as np
import random
import math

class QCloud:
    def __init__(self, env, devices, job_records_manager, allocation_mode="simple", printlog=True):
        """
        Initializes the QCloud class.

        Parameters:
        - env: The SimPy environment.
        - devices: The list of quantum devices in the cloud.
        """
        self.env = env
        self.devices = devices
        self.job_records = {}  # Dictionary to track job lifecycle events
        self.job_records_manager = job_records_manager
        # self.error_aware = False
        self.printlog = printlog

        # Mapping strategies to functions
        self.allocation_strategies = {
            "fast": self.simple_allocate_large_job,
            "smart": self.smart_allocate_large_job
        }

        # Set the allocation mode
        if allocation_mode in self.allocation_strategies:
            self.allocation_function = self.allocation_strategies[allocation_mode]
        else:
            raise ValueError(f"Invalid allocation mode: {allocation_mode}. Choose from {list(self.allocation_strategies.keys())}.")        

    def allocate_job(self, job, devices):
        """
        Dynamically calls the selected job allocation function.

        Parameters:
        - job: The QJob object representing the job.
        - devices: List of quantum devices.
        """
        return self.allocation_function(job, devices)
    
    def log_job_event(self, job_id, event_type, timestamp):
        """
        Logs a job event with a timestamp.

        Parameters:
        - job_id: The ID of the job.
        - event_type: The type of event ('arrival', 'start', or 'finish').
        """
        if job_id not in self.job_records:
            self.job_records[job_id] = {}
        self.job_records[job_id][event_type] = timestamp

    def get_event_logger(self):
        """
        Returns a callback function for logging job events.
        """
        return self.log_job_event

    def device_comm(self, job, device1, device2, qubits_required, feedback=False):
        comm_time = qubits_required * 0.02  # Adjust communication latency
        if self.printlog:
            print(f"{self.env.now:.2f}: Communication between {device1.name} and {device2.name} started.")
        
        self.job_records_manager.log_job_event(job.job_id, 'comm_time', round(comm_time,4))
        
        yield self.env.timeout(comm_time)  # Simulate delay

        if feedback:
            # Example: Simulate a feedback-dependent operation
            if self.printlog:
                print(f"{self.env.now:.2f}: Measurement feedback received. Adjusting circuit on {device2.name}.")
            yield self.env.timeout(0.02)  # Simulate classical computation delay
        if self.printlog:
            print(f"{self.env.now:.2f}: Communication between {device1.name} and {device2.name} finished.")
 
    def calculate_process_time(self, device, job):
        """
        Calculate processing time considering IBM-specific metrics.
        """
        M = 100
        K = 10
        S = job.num_shots
        D = math.log2(device.qvol)

        return  M * K * S * D / device.clops / 60
    
    def simple_allocate_large_job(self, job, devices):
        """
        Allocate a large job across multiple devices with error-aware or error-agnostic scheduling.

        Parameters:
        - job: The QJob object representing the job.
        - devices: List of quantum devices.
        """
        if self.printlog:
            for d in devices: 
                print(f"Available qubits for {d.name}: {d.container.level}, CLOPS: {d.clops}, ERR: {d.error_score}")

        # Step 1: Identify eligible devices
        eligible_devices = []
        for device in devices:
            if device.container.level >= job.num_qubits / len(devices):
                selected_subgraph = select_vertices_fast(device, job.num_qubits // len(devices), job.job_id)
                if selected_subgraph:                    
                    eligible_devices.append((device, selected_subgraph, device.error_score, device.clops))

        # Step 2: Ensure sufficient devices are available
        while len(eligible_devices) < 2:
            if self.printlog:
                print(f"{self.env.now:.2f}: Insufficient connected devices to allocate job #{job.job_id}. Retrying...")
            yield self.env.timeout(1)
            eligible_devices = []
            for device in devices:
                if device.container.level >= job.num_qubits / len(devices):
                    selected_subgraph = select_vertices_fast(device, job.num_qubits // len(devices), job.job_id)
                    if selected_subgraph:
                        eligible_devices.append((device, selected_subgraph, device.error_score, device.clops))


        # Step 3: Select devices to allocate
        split_qubits = job.num_qubits // len(eligible_devices)
        remainder_qubits = job.num_qubits % len(eligible_devices)
        allocated_devices = []
        
        # Step 4: Split job across selected devices optimally
        for idx, (device, subgraph, error_score, clops) in enumerate(eligible_devices):
            allocated_qubits = split_qubits + (1 if idx < remainder_qubits else 0)
            with device.resource.request(priority=2) as req:
                yield device.container.get(allocated_qubits)
                allocated_devices.append((device, allocated_qubits, subgraph, clops))
                if self.printlog:
                    print(f"{self.env.now:.2f}: Job #{job.job_id} allocated {allocated_qubits} qubits on {device.name} (error score: {error_score:.4f}).")

                # Log per-device allocation start
                self.job_records_manager.log_job_event(job.job_id, 'devc_proc', round(self.env.now, 4))

        # Step 5: process inter-device communication by pairing devices 
        for i in range(len(allocated_devices) - 1):
            device1, qubits1, _, _ = allocated_devices[i]
            device2, qubits2, _, _ = allocated_devices[i + 1]
            yield self.env.process(self.device_comm(job, device1, device2, qubits1 + qubits2))

        # Step 6: Process communication time  
        process_times = [self.calculate_process_time(device, job) for device, _, _, _ in allocated_devices]
        yield self.env.timeout(max(process_times))  # Max execution time across devices

        # Step 7: Release resources after completion
        for device, allocated_qubits, _, _ in allocated_devices:
            yield device.container.put(allocated_qubits)
            self.job_records_manager.log_job_event(job.job_id, 'devc_finish', round(self.env.now, 4))
            if self.printlog:
                print(f"{self.env.now:.2f}: Job #{job.job_id} completed on {device.name}.")
             
        # Step 8: Compute Fidelity
        fidelities = []
        for device, _, _, _ in allocated_devices:  
            single_qubit_fidelity = (1 - device.avg_single_qubit_error) ** job.depth             
            readout_fidelity = (1 - device.avg_readout_error) ** ((job.num_qubits // len(eligible_devices)) ** 0.5 ) 
            device_fidelity = single_qubit_fidelity * readout_fidelity
            fidelities.append(device_fidelity)

        # Step 9: Compute final fidelity with communication penalty
        avg_fidelity = sum(fidelities) / len(fidelities) if fidelities else -1.0
        num_connections = len(allocated_devices) - 1  # Number of times devices communicate
        communication_penalty = 0.94 ** num_connections  # Decay for each communication
        final_fidelity = avg_fidelity * communication_penalty  # Final fidelity
        
        self.job_records_manager.log_job_event(job.job_id, 'fidelity', round(final_fidelity,4))
 


    def smart_allocate_large_job(self, job, devices):
        """
        Allocate a large job across multiple devices using either a simple or error-aware allocation strategy.

        Parameters:
        - job: The QJob object representing the job.
        - devices: List of quantum devices.
        """
        if self.printlog:
            for d in devices: 
                print(f"Available qubits for {d.name}: {d.container.level}, CLOPS: {d.clops}, ERR: {d.error_score}")

        # Step 1: Identify eligible devices
        eligible_devices = []
        for device in devices:
            if device.container.level >= job.num_qubits / len(devices):
                selected_subgraph = select_vertices_fast(device, job.num_qubits // len(devices), job.job_id)
                if selected_subgraph:   
                    eligible_devices.append((device, selected_subgraph, device.error_score, device.clops))
        
        # Step 2: Ensure sufficient devices are available
        while len(eligible_devices) < 2:
            if self.printlog:
                print(f"{self.env.now:.2f}: Insufficient connected devices to allocate job #{job.job_id}. Retrying...")
            yield self.env.timeout(1)
            eligible_devices = []
            for device in devices:
                if device.container.level >= job.num_qubits / len(devices):
                    selected_subgraph = select_vertices_fast(device, job.num_qubits // len(devices), job.job_id)
                    if selected_subgraph:
                        eligible_devices.append((device, selected_subgraph, device.error_score, device.clops))

        # Sort by lowest error score first then minimize the device usage
        eligible_devices.sort(key=lambda x: x[2])  

        num_devices_to_use = min(len(eligible_devices), math.ceil(job.num_qubits / max(d.container.level for d, _, _, _ in eligible_devices)))
        selected_devices = eligible_devices[:num_devices_to_use]  # Pick best devices

        # Step 3: Select devices to allocate
        split_qubits = job.num_qubits // num_devices_to_use
        remainder_qubits = job.num_qubits % num_devices_to_use
        allocated_devices = []
    
        # Step 4: Split job across selected devices optimally
        for idx, (device, subgraph, error_score, clops) in enumerate(selected_devices):
            allocated_qubits = split_qubits + (1 if idx < remainder_qubits else 0)
            with device.resource.request(priority=2) as req:
                yield device.container.get(allocated_qubits)
                allocated_devices.append((device, allocated_qubits, subgraph, clops))
                if self.printlog:
                    print(f"{self.env.now:.2f}: Job #{job.job_id} allocated {allocated_qubits} qubits on {device.name} (error score: {error_score:.4f}).")

                # Log per-device allocation start
                self.job_records_manager.log_job_event(job.job_id, 'devc_proc', round(self.env.now, 4))

        # Step 5: process inter-device communication by pairing devices 
        for i in range(len(allocated_devices) - 1):
            device1, qubits1, _, _ = allocated_devices[i]
            device2, qubits2, _, _ = allocated_devices[i + 1]
            yield self.env.process(self.device_comm(job, device1, device2, qubits1 + qubits2))

        # Step 6: Process communication time  
        process_times = [self.calculate_process_time(device, job) for device, _, _, _ in allocated_devices]
        yield self.env.timeout(max(process_times))

        # Step 7: Release resources after completion
        for device, allocated_qubits, _, _ in allocated_devices:
            yield device.container.put(allocated_qubits)
            self.job_records_manager.log_job_event(job.job_id, 'devc_finish', round(self.env.now, 4))
            if self.printlog:
                print(f"{self.env.now:.2f}: Job #{job.job_id} completed on {device.name}.")

        # Step 8: Compute Fidelity
        fidelities = []
        for device, _, _, _ in allocated_devices:
            single_qubit_fidelity = (1 - device.avg_single_qubit_error) ** job.depth
            readout_fidelity = (1 - device.avg_readout_error) ** ( (job.num_qubits // len(allocated_devices)) ** 0.5 )
            device_fidelity = single_qubit_fidelity * readout_fidelity
            fidelities.append(device_fidelity)

        # Step 9: Compute final fidelity with communication penalty
        avg_fidelity = sum(fidelities) / len(fidelities) if fidelities else -1.0
        num_connections = len(allocated_devices) - 1  
        communication_penalty = 0.94 ** num_connections  
        final_fidelity = avg_fidelity * communication_penalty  

        self.job_records_manager.log_job_event(job.job_id, 'fidelity', round(final_fidelity,4))