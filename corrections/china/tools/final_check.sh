#!/bin/bash
# final_check.sh <dates...> — verify_cn + verify_report + check_cites per date, in parallel; one summary line per date.
cd "$(dirname "$0")/.."
one() {
  d=$1
  a=$(python3 -I tools/verify_cn.py $d 2>&1); b=$(python3 -I tools/verify_report.py $d 2>&1); c=$(python3 -I tools/check_cites.py $d 2>&1)
  s="-"; [ -f sectors/$d.html ] && s=$(python3 -I tools/verify_sectors.py $d 2>&1 | awk 'NR==1{r=$3} /WARN/{w++} END{printf "%s(%d warn)", r, w}')
  printf "%s cn=%s(%s warn) report=%s(%s warn) %s | cites_unmatched=%s | sectors=%s\n" $d \
    "$(echo "$a" | head -1 | grep -o 'PASS\|FAIL')" "$(echo "$a" | grep -c WARN)" \
    "$(echo "$b" | head -1 | grep -o 'PASS\|FAIL')" "$(echo "$b" | grep -c WARN)" \
    "$(echo "$b" | head -1 | grep -o 'left: [0-9]*, was [0-9]*')" "$(echo "$c" | grep -c 'NO MATCH')" "$s"
}
export -f one
printf "%s\n" "$@" | xargs -P 8 -I{} bash -c 'one {}'
