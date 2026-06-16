import ai_blue from './generated/ai-blue.svg'
import ai_white from './generated/ai-white.svg'
import back_ink from './generated/back-ink.svg'
import ball_blue from './generated/ball-blue.svg'
import ball_muted from './generated/ball-muted.svg'
import chart_blue from './generated/chart-blue.svg'
import chart_muted from './generated/chart-muted.svg'
import chart_gray from './generated/chart-gray.svg'
import chevron_blue from './generated/chevron-blue.svg'
import chevron_muted from './generated/chevron-muted.svg'
import clock_slate from './generated/clock-slate.svg'
import clock_muted from './generated/clock-muted.svg'
import clock_gray from './generated/clock-gray.svg'
import defense_blue from './generated/defense-blue.svg'
import group_blue from './generated/group-blue.svg'
import info_slate from './generated/info-slate.svg'
import medal_amber from './generated/medal-amber.svg'
import medal_muted from './generated/medal-muted.svg'
import refresh_blue from './generated/refresh-blue.svg'
import share_blue from './generated/share-blue.svg'
import shield_blue from './generated/shield-blue.svg'
import shield_red from './generated/shield-red.svg'
import shield_muted from './generated/shield-muted.svg'
import spark_blue from './generated/spark-blue.svg'
import stability_blue from './generated/stability-blue.svg'
import star_ink from './generated/star-ink.svg'
import target_blue from './generated/target-blue.svg'
import team_blue from './generated/team-blue.svg'
import trophy_blue from './generated/trophy-blue.svg'
import trophy_green from './generated/trophy-green.svg'
import trophy_muted from './generated/trophy-muted.svg'

export type IconTone = 'blue' | 'slate' | 'muted' | 'ink' | 'white' | 'green' | 'red' | 'gray' | 'amber'

export const localIconAssets = {
  ai: {
    blue: ai_blue,
    white: ai_white
  },
  back: {
    ink: back_ink
  },
  ball: {
    blue: ball_blue,
    muted: ball_muted
  },
  chart: {
    blue: chart_blue,
    muted: chart_muted,
    gray: chart_gray
  },
  chevron: {
    blue: chevron_blue,
    muted: chevron_muted
  },
  clock: {
    slate: clock_slate,
    muted: clock_muted,
    gray: clock_gray
  },
  defense: {
    blue: defense_blue
  },
  group: {
    blue: group_blue
  },
  info: {
    slate: info_slate
  },
  medal: {
    amber: medal_amber,
    muted: medal_muted
  },
  refresh: {
    blue: refresh_blue
  },
  share: {
    blue: share_blue
  },
  shield: {
    blue: shield_blue,
    red: shield_red,
    muted: shield_muted
  },
  spark: {
    blue: spark_blue
  },
  stability: {
    blue: stability_blue
  },
  star: {
    ink: star_ink
  },
  target: {
    blue: target_blue
  },
  team: {
    blue: team_blue
  },
  trophy: {
    blue: trophy_blue,
    green: trophy_green,
    muted: trophy_muted
  }
} as const
