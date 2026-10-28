string WAIT_STOP=WAIT_STOP
string WAIT_POSITION=WAIT_POSITION
string RECONCILING=RECONCILING
string READY=READY

string server_epoch
uint64 state_sequence
string phase
# TrafficCodes.REASON_*; this topic is not a movement permission.
string reason_code
string zone_revision
farm_interfaces/TrafficRegistration[] robots
