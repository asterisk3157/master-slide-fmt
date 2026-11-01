on run argv
  set f to item 1 of argv
  set o to item 2 of argv
  with timeout of 100 seconds
    tell application "Microsoft PowerPoint"
      open (POSIX file f)
      delay 5
      save active presentation in (POSIX file o) as save as PDF
      delay 3
      close active presentation saving no
    end tell
  end timeout
end run
