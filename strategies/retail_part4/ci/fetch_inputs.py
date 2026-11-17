"""Fetch a single coherent input snapshot before preparation; never refetch after freezing."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    protocol=json.loads((ROOT/"protocol.json").read_text())
    calendar=protocol["source_calendar"]
    ends={cfg["end"] for cfg in protocol["case_config"].values()}
    assert ends=={calendar["end"]}, "All approved cases must share the source-calendar endpoint"
    assert calendar["start"]==min(cfg["source_min"] for cfg in protocol["case_config"].values())
    collections=protocol.get("source_collections",{})
    assert len(collections)<=1,"This fixed study supports one connected collection"
    command=[sys.executable,str(ROOT/"source_tools/fetch_public_sources.py"),"--root",str(ROOT),"--start",calendar["start"],"--end",calendar["end"]]
    for day in calendar.get("extra_dates",[]):command+=["--extra-date",day]
    for path,meta in collections.items():
        actual=(ROOT/path).resolve()
        assert ROOT in actual.parents and actual.is_file(),"Configured collection must be supplied below the study root"
        command+=["--collection-file",path,"--collection-start",meta["start"],"--collection-end",meta["end"],"--collection-sha256",meta["sha256"]]
    subprocess.run(command,cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/"market/fetch_prices.py"),"--root",str(ROOT),"--start","2023-01-01","--end",calendar["end"]],cwd=ROOT,check=True)
if __name__=="__main__":main()
