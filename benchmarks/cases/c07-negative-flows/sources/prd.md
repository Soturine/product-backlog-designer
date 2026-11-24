# PRD — Community Fridge Kiosk (fictitious)

## Requirements
R1 A registered member scans their badge to unlock the fridge door.
R2 An unknown or deactivated badge does not unlock the door, and the screen shows "Badge not recognized".
R3 A member may take at most 3 items per day.
R4 Taking a fourth item on the same day is recorded and the member sees a warning; the member is not locked out.
R5 If the door stays open for more than 60 seconds, an audible alert sounds until the door is closed.
R6 If the kiosk loses connectivity, badge checks use the last synchronized member list, and events are uploaded when connectivity returns.
R7 Volunteers can mark an item as expired; expired items are removed from the available inventory count.

## Out of scope
Payments and donations tracking.
