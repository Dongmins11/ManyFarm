# Mobile coordination state (3.0.0). Both peers must use the same IDL.
# Periodic measured base/transfer state is required for hardware plugins.
builtin_interfaces/Time stamp
string robot_id
string boot_id
uint64 sequence
bool base_stopped
bool transfer_active
