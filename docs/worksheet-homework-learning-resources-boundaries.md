# Worksheet, Homework, and Learning Resource Boundaries

These concepts are separate and must not share commands or persistence paths.

## External Worksheet Collection

`worksheet_url` is an optional external worksheet collection or assignment
document pack. It remains in the active class and term General Links config.

- Student commands: `งาน`, `ใบงาน`.
- Persistence: `classes/{classId}/terms/{activeTermId}/config/links`.
- Dashboard: General Links Editor.
- Missing configuration: return a safe unavailable message.

## Persisted Homework

Homework records are assignments stored by MTC Assistant.

- Create command: `บันทึกการบ้าน`.
- List command: `การบ้าน`.
- Persistence: class-scoped homework for class-aware users, with the root
  collection retained only for legacy behavior.
- `การบ้าน` must not resolve to `worksheet_url`.

## Learning Resources

Learning resources are subject, term, and grade-aware materials such as
textbook solutions.

- Student commands include `ชีวะ` and `ฟิสิกส์`.
- Persistence: `classes/{classId}/terms/{activeTermId}/resources`.
- Biology and physics URLs must come from this system.
- Classroom Knowledge must not embed legacy biology or physics URLs.

Do not merge these concepts or migrate `worksheet_url` into learning resources
without a separate product and data-migration decision.
