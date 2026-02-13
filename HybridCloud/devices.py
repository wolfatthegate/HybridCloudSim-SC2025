# devices.py

import simpy
import random

class CPU:
    def __init__(self, name, env=None, cpu_capacity=100, mem_bw_capacity=200):
        """
        cpu_capacity:    total CPU units (integer)
        mem_bw_capacity: total memory bandwidth units (e.g., MB/s 'units') (integer)
        """
        self.name = name
        self.type = "CPU"
        self.env = None
        self.queue = None
        self.container = None           # CPU units
        self.mem_bw = None              # memory bandwidth units
        self.resource = None
        self.cpu_capacity = int(cpu_capacity)
        self.mem_bw_capacity = int(mem_bw_capacity)
        if env is not None:
            self.assign_env(env)

    def assign_env(self, env):
        self.env = env
        self.queue = simpy.Resource(env, capacity=1)
        self.container = simpy.Container(env=env, capacity=self.cpu_capacity, init=self.cpu_capacity)
        self.mem_bw   = simpy.Container(env=env, capacity=self.mem_bw_capacity, init=self.mem_bw_capacity) 
        self.resource = simpy.PriorityResource(env=env, capacity=1)

    def maintenance(self, _):
        return self.env.timeout(0)  
            
    def process_job(self, job, wait_time_start):
        job_id = job.job_id
        duration = random.uniform(1, 3)
        cpu_units = random.randint(4, 10)
        mem_bw    = int(getattr(job, "mem_bw",  20))
        
        self.job_records_manager.log_job_event(job_id, 'devc_name', self.name)
        # phase arrival
        self.job_records_manager.log_job_event(job_id, 'cpu_arrive', round(self.env.now, 4))
        self.job_records_manager.log_job_event(job.job_id, 'cpu_units', cpu_units)
        self.job_records_manager.log_job_event(job_id, 'cpu_mem_bw', mem_bw)
        
        yield self.container.get(cpu_units)
        try:
            yield self.mem_bw.get(mem_bw)
        except:
            # If mem_bw get fails for some reason, give CPU units back and re-raise
            yield self.container.put(cpu_units)
            raise
            
        # service start
        # self.job_records_manager.log_job_event(job_id, 'cpu_start', round(self.env.now, 4))
        
        # print(f"{self.env.now:.2f}: Job {job_id} running on {self.name} for {duration:.1f} (cpu_units={cpu_units}, mem_bw={mem_bw})")

        yield self.env.timeout(duration)

        # service finish
        # self.job_records_manager.log_job_event(job_id, 'cpu_finish', round(self.env.now, 4))
        
        # print(f"{self.env.now:.2f}: Job {job.job_id} finished running on {self.name} for {duration:.1f}")

        # Publish a 'device_finish' event
        self.event_bus.publish("device_finish", {
            "device": self.name,
            "job_id": job_id,
            "timestamp": round(self.env.now, 2),
        })
        
        # always return capacity
        try:
            yield self.container.put(cpu_units)
            yield self.mem_bw.put(mem_bw)
        except Exception as e:
            print(f"{self.env.now:.2f}: ERROR while returning units for Job {job.job_id} on {self.name}: {e}")            