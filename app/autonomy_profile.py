"""The private owner's goal recovery preference, preserving other profile settings."""
from bootstrap import HOME,PRIVATE


def sync_goal_autonomy():
    if not PRIVATE:
        return False
    from hermes_cli.config import read_user_config_raw
    from utils import atomic_roundtrip_yaml_update
    path=HOME/'config.yaml'
    config=read_user_config_raw(path)
    goals=dict(config.get('goals') or {})
    updated={**goals,'continue_failed_gates':True,'verify_reported_files':True,'verify_tool_evidence':True}
    updated.setdefault('max_turns',0)
    if updated==goals:
        return False
    atomic_roundtrip_yaml_update(path,'goals',updated)
    return True
