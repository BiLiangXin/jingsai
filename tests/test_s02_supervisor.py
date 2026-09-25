"""Stdlib-only supervisor timeout/exception regressions; no process launched."""
import datetime,importlib.util,json,sys
from pathlib import Path
from unittest.mock import Mock,patch
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('s02_supervisor_test',ROOT/'tools/s02_supervise.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls,tz=None):return cls(2026,9,25,2,0,tzinfo=datetime.timezone.utc)
def args(tmp_path):
    return ['supervise','--source',str(tmp_path/'NO_DATA'),'--output-dir',str(tmp_path/'campaign'),
        '--backup',str(tmp_path/'NO_BACKUP'),'--receipt-dir',str(tmp_path/'receipt')]
def test_setup_time_counts_toward_cap(tmp_path):
    proc=Mock();proc.wait.return_value=0;proc.poll.return_value=0
    with patch.object(sys,'argv',args(tmp_path)),patch.object(M.datetime,'datetime',FixedDateTime),patch.object(M.time,'monotonic',side_effect=[100.,103.]),patch.object(M.subprocess,'Popen',return_value=proc):
        assert M.main()==0
    proc.wait.assert_called_once_with(timeout=14397.);proc.kill.assert_not_called()
def test_unexpected_wait_exception_kills_owned_child(tmp_path):
    proc=Mock();proc.wait.side_effect=[KeyboardInterrupt(),0];proc.poll.return_value=None
    with patch.object(sys,'argv',args(tmp_path)),patch.object(M.datetime,'datetime',FixedDateTime),patch.object(M.time,'monotonic',side_effect=[100.,101.]),patch.object(M.subprocess,'Popen',return_value=proc),pytest.raises(KeyboardInterrupt):
        M.main()
    proc.kill.assert_called_once();assert proc.wait.call_count==2
def test_timeout_records_forced_stop(tmp_path):
    proc=Mock();proc.wait.side_effect=[M.subprocess.TimeoutExpired('synthetic',1),-1];proc.poll.return_value=-1
    with patch.object(sys,'argv',args(tmp_path)),patch.object(M.datetime,'datetime',FixedDateTime),patch.object(M.time,'monotonic',side_effect=[100.,101.]),patch.object(M.subprocess,'Popen',return_value=proc):
        assert M.main()==2
    assert json.loads((tmp_path/'receipt/exit.json').read_text())['forced_resource_stop'] is True
    proc.kill.assert_called_once()
