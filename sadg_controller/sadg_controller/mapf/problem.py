import subprocess
from logging import Logger
from tempfile import mkdtemp
from typing import Dict, List

import yaml

from sadg_controller.mapf.plan import Plan
from sadg_controller.mapf.roadmap import Roadmap
from sadg_controller.mapf.roadmap_location import RoadmapLocation

# from rclpy.node import Node


yaml.Dumper.ignore_aliases = lambda *args: True


class MAPFProblem:
    def __init__(
        self,
        roadmap: Roadmap,
        starts: List[RoadmapLocation],
        goals: List[RoadmapLocation],
        logger: Logger,
    ) -> None:
        self.roadmap = roadmap
        self.starts = starts
        self.goals = goals
        self.logger = logger
        self.tmp_dir = mkdtemp(prefix="sadg_controller")

    def solve(self, suboptimality_factor: float = 1.5) -> Plan:
        """Solve the MAPF problem using ECBS algorithm."""

        self.logger.info("Solving MAPF problem ...")

        # create dict from roadmap
        map_data = self.roadmap.get_map_data()

        # create dict from AGV start/goal locations
        agv_data = self._get_agv_data()

        # write to yaml file
        input_file = f"{self.tmp_dir}/input.yaml"
        ecbs_input = {
            "map": map_data,
            "agents": agv_data,
        }
        write_yaml(input_file, ecbs_input, self.logger)

        # solve MAPF using the generated yaml file
        solution_file = f"{self.tmp_dir}/solution.yaml"
        cmd = [
            "ecbs",
            "-i",
            input_file,
            "-o",
            solution_file,
            "-w",
            str(suboptimality_factor),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.stdout == "Planning NOT successful!\n":
            self.logger.error("Planning not successful!")
            raise RuntimeError("MAPF Planning not successful!")

        # read solution
        solution = read_yaml(solution_file, self.logger)

        # get map dimensions
        dimensions = self.roadmap.get_dimensions()

        return Plan(solution, dimensions)

    def _get_agv_data(self) -> Dict:

        agv_data = []
        for idx, (start, goal) in enumerate(zip(self.starts, self.goals)):

            agv_data.append(
                {
                    "name": f"agent{idx}",
                    "start": start.get_row_col(),
                    "goal": goal.get_row_col(),
                }
            )

        return agv_data


def write_yaml(file: str, payload: Dict, logger) -> None:
    logger.debug(f"Writing yaml file: {file} ...")
    with open(file, "w") as stream:
        yaml.dump(payload, stream, default_flow_style=False)


def read_yaml(file: str, logger) -> Dict:
    logger.debug(f"Reading yaml file: {file} ...")
    with open(file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)