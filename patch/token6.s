| rung 4 helper — the 6-channel dTD token / length computation.
|
| Replaces 0x40002a42..0x40002a4b (10 bytes) in FUN_40002912's slot-complete
| path. Stock (already x16 from the 4-channel patch) is:
|
|     moveq   #20,%d1        ; 16 + 4
|     movea.l %d0,%a0        ; a0 = the dTD  <-- d0 is the POINTER here
|     move.l  %d4,%d0        ; d0 = frames
|     lsl.l   %d1,%d4        ; d4 = (frames*16) << 16
|     lsl.l   #4,%d0         ; d0 = frames*16  -> length field
|
| For six channels both become frames*24 = (frames<<4)+(frames<<3).
| Order matters: a0 must be taken from the incoming d0 BEFORE d0 is reloaded
| from d4, or everything downstream (0x40002a52 onwards) writes to the wrong
| address.
|
| Downstream expects: a0 = dTD, d4 = byte count << 16, d0 = byte count.

        .text
        .global token6_helper
        .equ RETURN, 0x40002a4c

token6_helper:
        movea.l %d0,%a0                 | a0 = dTD, before d0 is reused
        move.l  %d4,%d0                 | d0 = frames
        move.l  %d0,%d1
        lsl.l   #4,%d0                  | frames*16
        lsl.l   #3,%d1                  | frames*8
        add.l   %d1,%d0                 | frames*24 = the length field
        move.l  %d0,%d4
        swap    %d4                      | d4 = (frames*24) << 16
        clr.w   %d4
        jmp     RETURN
