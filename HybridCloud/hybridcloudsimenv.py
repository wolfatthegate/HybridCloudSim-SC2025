# hybridcloudsimenv.py

from HybridCloud import *
from HybridCloud.job_generator import JobGenerator
from HybridCloud.hybridcloud import HybridCloud

class HybridCloudSimEnv(simpy.Environment):
    def __init__(self, qpu_devices, cpu_devices, broker_class=ParallelBroker, job_feed_method='generator', job_generation_model=None, file_path=None, printlog = False):
        """
        Initialize the hybrid simulation environment.

        Parameters:
        - qpu_devices: List of quantum devices.
        - cpu_devices: List of classical CPU devices.
        - broker_class: Class of the broker to use for job handling.
        - job_feed_method: 'generator' or 'dispatcher'.
        - job_generation_model: Callable for job inter-arrival times.
        - file_path: Path to CSV if using dispatcher mode.
        """
        super().__init__()
        self.qpu_devices = qpu_devices
        self.cpu_devices = cpu_devices
        self.broker_class = broker_class
        self.job_feed_method = job_feed_method
        self.job_generation_model = job_generation_model
        self.file_path = file_path
        self.printlog = printlog
        self.event_bus = EventBus()
        self.job_records_manager = JobRecordsManager(self.event_bus)

        self.qcloud = HybridCloud(
            env=self,
            qpu_devices=self.qpu_devices,
            cpu_devices=self.cpu_devices,
            job_records_manager=self.job_records_manager
        )

        self.job_generator = None
        self._initialize_devices()
        self._initialize_job_generator()

    def _initialize_devices(self):

        for device in self.qpu_devices + self.cpu_devices:
            device.assign_env(self)
            device.job_records_manager = self.job_records_manager
            device.event_bus = self.event_bus
            # self.process(device.maintenance(False))

    def _initialize_job_generator(self):

        self.job_generator = JobGenerator(
            env=self,
            broker_class=self.broker_class,
            devices=self.qpu_devices + self.cpu_devices,  # pass all devices
            job_records_manager=self.job_records_manager,
            event_bus=self.event_bus,
            qcloud=self.qcloud,
            method=self.job_feed_method,
            job_generation_model=self.job_generation_model,
            file_path=self.file_path,
            printlog=self.printlog
        )

    def run(self, until=None):
        self.process(self.job_generator.run())
        print(f"{self.now:.2f}: SIMULATION STARTED")
        super().run(until=until if until is not None else None)
        # After run: print a summary of jobs seen vs finished
        try:
            recs = self.job_records_manager.records  # or however you access them
            finished = [j for j, r in recs.items() if r.get("cpu_finish") or r.get("qpu_finish")]
            print(f"Jobs finished: {finished}")
        except Exception:
            pass
        finally: 
            print(f"{self.now:.2f}: SIMULATION ENDED")