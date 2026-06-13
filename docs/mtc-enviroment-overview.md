# MTC Enviroment Overview

## Canonical Product Map

The official umbrella name is **MTC Enviroment**. This spelling is intentional.

MTC Enviroment has exactly three top-level products:

1. **MTC Assistant**
2. **MTC the Game**, also acceptable as **MTC Game**
3. **Math Talent**
   - **MTC Cipher**, preferably available at `/labs/cipher`

MTC Cipher is a feature and route inside Math Talent. It is not a top-level
product.

MTC Hub has been removed from the active plan. It must not appear in the active
product hierarchy.

MTC Enviroment is not official school infrastructure and must not be presented
as such.

## Product Boundaries

### MTC Assistant

MTC Assistant contains:

- the LINE Bot, which remains the main student interface;
- the Flask backend and policy boundary;
- Firebase Firestore as the classroom data store; and
- MTC Dashboard as the admin command center.

MTC Assistant evolves toward MTC OS. MTC OS applies only to MTC Assistant. It
does not contain MTC the Game or Math Talent.

### MTC the Game

MTC the Game is a separate-repository web game for a small private friend
group. It is not a social network, community platform, or production-critical
MTC Assistant component.

### Math Talent

Math Talent is a separate-repository math website environment containing
multiple math features and interactive labs. MTC Cipher belongs inside Math
Talent.

## Repository and Availability Boundaries

Each top-level product has an independent repository and runtime boundary.
MTC Assistant must remain operational when Math Talent or MTC the Game is
unavailable. Cross-product outages must not block LINE webhook handling,
classroom data access, Dashboard administration, or MTC Assistant health
checks.

Do not create shared runtime dependencies merely to make the products appear
connected. Shared authentication, shared progress, or shared databases require
a separate reviewed decision.

## Link-First Integration

This link-first integration means MTC Assistant may present a verified HTTPS link to
another product without depending on that product's runtime or data model.

The initial integration direction is:

- MTC Assistant links to Math Talent and MTC Cipher where useful.
- MTC Assistant may link to MTC the Game as a separate optional experience.
- External links use safe fallback text when unavailable.
- No remote product becomes a prerequisite for a core MTC Assistant workflow.

MTC Cipher may integrate more deeply with MTC Assistant later. The first step
remains a link, not progress synchronization or shared identity.
