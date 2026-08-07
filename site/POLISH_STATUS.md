# Website polish status

Track for the 120s polish loop. Set `satisfied=true` only when **all** checklist items pass.

```
satisfied=false
fires_no_fix=0
last_fire=
last_fix=
```

## Checklist (all must be true)

- [ ] Loads board.json over http; meta chips show live counts
- [ ] Search filters ideas by company / idea / problem text
- [ ] Market + wedge type + fit + decision-grade filters work
- [ ] Drawer opens with primary, shortlist, problem, product, competitive
- [ ] Patterns / Markets / Infra views usable
- [ ] Keyboard: `/` focuses search, `Esc` closes drawer
- [ ] Mobile layout: rail stacks, cards single-column, drawer full-width OK
- [ ] Contrast readable; no purple-gradient SaaS default look
- [ ] Empty state when filters match nothing
- [ ] Export script regenerates board.json from sid.db
- [ ] README documents how to serve the site
- [ ] No console errors on load (smoke in browser or curl HTML/JS/CSS/JSON)

## Stop condition

When every checklist item is `[x]` **and** two consecutive fires report `quality_fix=none` after verification, set:

```
satisfied=true
```

Then call `scheduler_delete` on the website polish task_id.
