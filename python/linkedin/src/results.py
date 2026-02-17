from dataclasses                    import dataclass

@dataclass
class UpdateResults:
    success:    bool
    newJobs:    int
    uniqueJobs: int
