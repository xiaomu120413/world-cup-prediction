# Miniapp M1 Design QA

## Scope

- Build target: Taro React miniapp shell with H5 preview and WeChat miniapp build.
- Screens checked:
  - Home match briefing
  - Match AI report
  - Group standings
  - Prediction rankings
  - Team detail

## Visual Checks

| Check | Result | Notes |
| --- | --- | --- |
| Mobile viewport width | Pass | Verified at 390 x 844. `documentElement.scrollWidth` and `body.scrollWidth` remain 390 on all checked pages. |
| Main navigation | Pass | Bottom navigation displays 4 entries on list/ranking/team screens. Match report is a detail screen without bottom navigation. |
| Key content density | Pass | Home screen shows today's featured match, probability summary, upcoming matches, and champion probability without relying on a landing page. |
| Text overflow | Pass | Probability labels and list rows fit the tested viewport. |
| Design direction match | Pass | Uses the selected analyst-report direction: compact sports data UI, AI explanation cards, probability bars, and dense scan-friendly rows. |

## 2026-06-15 Regression

| Check | Result | Notes |
| --- | --- | --- |
| H5 browser title | Pass | Added UTF-8 charset so the browser title displays `世界杯预测` correctly. |
| Core route smoke | Pass | Checked five H5 routes at 390 x 844 and 1280 x 720; no horizontal overflow. |
| Detail entry click | Pass | Home `查看 AI 赛前报告` navigates to match detail. |
| Bottom navigation click | Pass | Added stable `data-testid` attributes and verified all four bottom navigation routes. |
| Console errors | Pass | No browser console errors observed during smoke test. |

## Verification Commands

```bash
npm.cmd run typecheck
npm.cmd run build:h5
npm.cmd run build:weapp
```

## Known Follow-Ups

- H5 build reports the default Taro entrypoint size warning at about 287 KiB; this is acceptable for M1 but should be optimized before a public H5 release.
- `npm install` reports dependency audit issues from the Taro/webpack dependency tree; review package upgrades during the infrastructure hardening milestone.
