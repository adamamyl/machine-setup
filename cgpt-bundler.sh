#!/usr/bin/env bash
shopt -s globstar
rm -f ~/bundle.txt

for f in **/**/*.py; do
  echo "===== START FILE: $f =====" >> ~/bundle.txt
  cat "$f" >> ~/bundle.txt
  echo -e "\n===== END FILE: $f =====\n" >> ~/bundle.txt
done

pbcopy < ~/bundle.txt
