# General Links Firestore-first Manual Test Record

## Summary

- Test date: 2026-06-01
- Result: passed
- Scope: class-aware general links config, MTC12 legacy solution link preservation, and MTC13 solution-link blocking.

## Deployment/Commit Context

- `6bd502c feat: load class-aware general links config`
- `9b4ea61 fix: preserve mtc12 legacy solution links`

## Behavior Verified

### MTC12

- `ลิงก์` passed.
- `เว็บโรงเรียน` passed.
- `เกรด` passed.
- `ลา` passed.
- `งาน` / `ใบงาน` passed.
- `ชีวะ` returns the legacy biology solution link.
- `ฟิสิกส์` returns the legacy physics solution link.
- Flex menu biology/physics buttons still work as legacy URLs.

### MTC13

- `ลิงก์` passed.
- `เว็บโรงเรียน` passed.
- `เกรด` passed.
- `ลา` passed.
- `งาน` / `ใบงาน` behavior is safe when `worksheet_url` is missing.
- `ชีวะ` does not return the MTC12 biology solution link.
- `ฟิสิกส์` does not return the MTC12 physics solution link.
- Flex menu does not expose MTC12 biology/physics solution URLs.

## Known Limitations

- Biology/physics solution links are still legacy MTC12-only.
- A proper learning resources system is not implemented yet.
- Flex menu still visually contains the `เฉลยวิชา` section, but MTC13 uses safe message actions rather than MTC12 URLs.
- Dashboard editor for links is not implemented yet.

## Follow-up Tasks

- Add Learning Resources foundation later.
- Move subject-specific solution resources out of legacy commands.
- Add dashboard editing for class/term links later.
- Consider cleaning up Flex menu information architecture after resources exist.
