"""Named command entry point for the isolated mapped-sector Part 4 strategy."""
from __future__ import annotations
import argparse,subprocess,sys
from pathlib import Path
STRATEGY_ID="mapp_strategy"
ROOT=Path(__file__).resolve().parent
COMMANDS={
    "relative-clock":("ci/run_relative_clock.py",[],"Compare absolute/relative SMA20 and reservation-after-fill rules across the three hedge policies"),
    "extended-history":("ci/run_extended_history.py",[],"Run the three policies on extended history with explicit missing-month entry blocking"),
    "stoploss-sensitivity":("ci/stoploss_sensitivity.py",[],"Re-simulate unhedged25 from a completed extended-history run with -5/-8/-10% stops"),
    "fetch":("ci/fetch_inputs.py",[],"Fetch the one approved local source/price snapshot"),
    "prepare":("prepare_study.py",[],"Prepare fixed schedules and freeze exact inputs"),
    "preflight":("ci/check_study.py",["--preflight"],"Independently verify inputs before returns"),
    "backtest":("run_study.py",[],"Run nine fixed books; requires --execute and --expected-freeze"),
    "audit":("ci/check_study.py",["--ledger"],"Independently verify the saved nine-book ledgers"),
    "plot":("plot_results.py",["--expected-cases","9","--main-corpus","november_continuous","--audit-json","diagnosis/independent_results.json"],"Render the main PnL and reconcile all nine books"),
    "export":("ci/export_approved_results.py",[],"Build the local approved simulated-output package"),
    "recorded-controls":("ci/run_recorded_controls.py",[],"Reprice only the recorded25 controls; requires --execute"),
}
def main():
    parser=argparse.ArgumentParser(prog="mapp_strategy.py",
        description="mapp_strategy: mapped-sector What Retail Is Playing Part 4 research.",
        epilog="Arguments after a command are forwarded unchanged. Use COMMAND --help for its options. Execution and complete-source gates remain mandatory; this entry point does not publish.")
    parser.add_argument("command",choices=COMMANDS,help="; ".join(key+": "+value[2] for key,value in COMMANDS.items()))
    argv=sys.argv[1:]
    if not argv or argv[0] in ["-h","--help"]:
        parser.print_help();return
    args=parser.parse_args(argv[:1])
    relative,options,_=COMMANDS[args.command]
    script=ROOT/relative
    if not script.is_file():raise SystemExit("Missing mapp_strategy component: "+relative)
    subprocess.run([sys.executable,str(script),*options,*argv[1:]],cwd=ROOT,check=True)
if __name__=="__main__":main()
