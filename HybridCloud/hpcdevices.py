class CPUDevice:
    def __init__(self, name, env):
        self.name = name
        self.env = env
        self.queue = simpy.Resource(env, capacity=1)

    def execute(self, job):
        exec_time = job.cpu_exec_time  # you can set this per job
        yield self.env.timeout(exec_time)