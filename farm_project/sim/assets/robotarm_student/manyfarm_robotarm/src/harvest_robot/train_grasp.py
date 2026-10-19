"""Dedicated approach-and-grasp PPO entry point."""
import sys
from run import main

if __name__ == "__main__":
    sys.argv[1:1] = ["train", "--task", "grasp"]
    main()
