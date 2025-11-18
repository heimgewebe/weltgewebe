| Domäne | Deutsch | Technik/API | Bedeutung |
|---|---|---|---|
| node | Knoten | /nodes | Orte, Ideen, Ressourcen |
| role | Rolle | /roles | Berechtigungs- und Identitätskontext für Aktionen im Gewebe |
| edge | Faden | /edges | Graph-Beziehungen zwischen node/role |
| conversation | Gesprächsraum | /conversations | Diskussions- / Entscheidungsräume |
| message | Beitrag | /conversations/{id}/messages | Einzelner Inhalt in einer conversation |

---

**`thread` ist vollständig verboten; jede frühere Verwendung muss in `edge` oder `conversation` überführt werden.**
