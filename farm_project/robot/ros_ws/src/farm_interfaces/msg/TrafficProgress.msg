string WAITING=WAITING
string MOVING=MOVING
string HOLDING=HOLDING
string EXITING=EXITING
string STOPPED_FAULT=STOPPED_FAULT
# Reserved for later docking/handoff. Not used in the first simulation.
string DOCKING=DOCKING
string TRANSFERRING=TRANSFERRING
string SYNC_NONE=NONE
string STOP_SENT=STOP_SENT
string POSITION_READY=POSITION_READY

farm_interfaces/TrafficContext context
string sync_id
string sync_stage
string registered_zone_revision
# Starts at 1 per boot; increases on each publication.
uint64 sequence
# Exact RobotStatus.sequence under the same robot_id and boot_id.
uint64 status_sequence
string traffic_state
# Advisory reports. Controller computes the final occupancy from the matched pose.
string[] occupied_zone_ids
string[] blocked_zone_ids
# First simulation: stop command sent, not measured zero velocity.
bool stopped
string reason_code
# ISO 8601 with timezone, for logging only; never a lease deadline.
string timestamp
