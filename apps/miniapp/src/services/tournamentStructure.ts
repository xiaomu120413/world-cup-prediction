import type { GroupData, GroupSummary, HomeData } from '@/services/data'
import type { GroupTeam } from '@/services/mock'
import { teamResources, type TeamResource } from '@/services/teamResources'

export type TournamentGroup = {
  id: string
  name: string
  teamIds: string[]
  summary: string
}

export type TournamentTeam = TeamResource & {
  groupId: string
  groupName: string
  seed: number
}

export const tournamentGroups: TournamentGroup[] = [
  {
    id: 'group-a',
    name: 'A组',
    teamIds: ['mexico', 'south-korea', 'czech', 'south-africa'],
    summary: '墨西哥和韩国出线优势明显，捷克仍保留第三名晋级机会。'
  },
  {
    id: 'group-b',
    name: 'B组',
    teamIds: ['france', 'norway', 'qatar', 'switzerland'],
    summary: '法国控制力领先，挪威和瑞士的小组第二争夺会很接近。'
  },
  {
    id: 'group-c',
    name: 'C组',
    teamIds: ['brazil', 'morocco', 'scotland', 'panama'],
    summary: '巴西纸面实力占优，摩洛哥反击效率会影响头名归属。'
  },
  {
    id: 'group-d',
    name: 'D组',
    teamIds: ['argentina', 'japan', 'ghana', 'haiti'],
    summary: '阿根廷晋级优势稳定，日本和加纳的直接对话权重最高。'
  },
  {
    id: 'group-e',
    name: 'E组',
    teamIds: ['spain', 'iran', 'tunisia', 'new-zealand'],
    summary: '西班牙控球优势明显，伊朗与突尼斯的防守质量决定第二集团。'
  },
  {
    id: 'group-f',
    name: 'F组',
    teamIds: ['england', 'senegal', 'saudi-arabia', 'bosnia-herzegovina'],
    summary: '英格兰和塞内加尔的强度领先，沙特与波黑需要抢首轮积分。'
  },
  {
    id: 'group-g',
    name: 'G组',
    teamIds: ['portugal', 'colombia', 'jordan', 'cape-verde'],
    summary: '葡萄牙进攻上限最高，哥伦比亚的转换效率会影响头名竞争。'
  },
  {
    id: 'group-h',
    name: 'H组',
    teamIds: ['netherlands', 'austria', 'iraq', 'curacao'],
    summary: '荷兰整体稳定性更好，奥地利具备直接竞争小组第一的空间。'
  },
  {
    id: 'group-i',
    name: 'I组',
    teamIds: ['belgium', 'australia', 'uzbekistan', 'algeria'],
    summary: '比利时经验占优，澳大利亚、乌兹别克斯坦和阿尔及利亚差距不大。'
  },
  {
    id: 'group-j',
    name: 'J组',
    teamIds: ['germany', 'ecuador', 'egypt', 'ivory-coast'],
    summary: '德国仍是头名热门，厄瓜多尔、埃及和科特迪瓦的身体对抗会拉高波动。'
  },
  {
    id: 'group-k',
    name: 'K组',
    teamIds: ['croatia', 'uruguay', 'canada', 'sweden'],
    summary: '克罗地亚与乌拉圭经验更足，加拿大和瑞典需要把握反击效率。'
  },
  {
    id: 'group-l',
    name: 'L组',
    teamIds: ['usa', 'paraguay', 'turkey', 'congo-dr'],
    summary: '美国主场加成明显，巴拉圭和土耳其会争夺第二晋级顺位。'
  }
]

const teamById = teamResources.reduce<Record<string, TeamResource>>((map, team) => {
  map[team.id] = team
  return map
}, {})

const records = ['1/0/0', '1/0/0', '0/0/1', '0/0/1']
const points = [3, 3, 0, 0]
const goals = ['2/0', '2/1', '1/2', '0/2']
const qualification = [98.5, 79.4, 51.2, 22.4]

function getGroup(groupId = 'group-a') {
  return tournamentGroups.find(group => group.id === groupId) || tournamentGroups[0]
}

function teamFromId(teamId: string) {
  return teamById[teamId] || {
    id: teamId,
    name: teamId,
    nameEn: teamId,
    flagCode: ''
  }
}

function groupOrder(groupId: string) {
  const index = tournamentGroups.findIndex(group => group.id === groupId)
  return index < 0 ? 0 : index
}

export const allTournamentTeams: TournamentTeam[] = tournamentGroups.flatMap(group =>
  group.teamIds.map((teamId, index) => ({
    ...teamFromId(teamId),
    groupId: group.id,
    groupName: group.name,
    seed: index + 1
  }))
)

export function getTeamGroupLabel(teamId = '') {
  return allTournamentTeams.find(team => team.id === teamId)?.groupName || '小组待同步'
}

export function getFallbackGroupSummaries(): GroupSummary[] {
  return tournamentGroups.map((group, index) => ({
    id: group.id,
    name: group.name,
    matchesFinished: index < 4 ? 2 : index < 8 ? 1 : 0,
    matchesTotal: 6,
    summary: group.summary
  }))
}

export function getFallbackGroupData(groupId = 'group-a'): GroupData {
  const group = getGroup(groupId)
  const offset = groupOrder(group.id) % 3
  const teams: GroupTeam[] = group.teamIds.map((teamId, index) => {
    const team = teamFromId(teamId)
    const adjustedQualification = Math.max(8, Math.min(99, qualification[index] - offset * (index + 1)))
    return {
      teamId: team.id,
      rank: index + 1,
      name: team.name,
      record: records[index],
      points: points[index],
      goals: goals[index],
      qualification: Number(adjustedQualification.toFixed(1))
    }
  })

  return {
    id: group.id,
    title: `${group.name}形势`,
    subtitle: `小组赛 · 已完成 ${groupOrder(group.id) < 4 ? 2 : groupOrder(group.id) < 8 ? 1 : 0}/6 场`,
    summary: group.summary,
    teams,
    updatedAt: '更新于 18:00',
    matchesFinished: groupOrder(group.id) < 4 ? 2 : groupOrder(group.id) < 8 ? 1 : 0,
    matchesTotal: 6
  }
}

export function getFallbackGroupMatches(groupId = 'group-a'): HomeData['upcomingMatches'] {
  const group = getGroup(groupId)
  const teams = group.teamIds.map(teamFromId)
  const day = 18 + (groupOrder(group.id) % 4)
  return [
    {
      id: `${group.id}-${teams[0].id}-${teams[1].id}`,
      home: teams[0].name,
      away: teams[1].name,
      time: `6月${day}日 21:00`,
      tendency: '第3轮',
      meta: '第3轮'
    },
    {
      id: `${group.id}-${teams[2].id}-${teams[3].id}`,
      home: teams[2].name,
      away: teams[3].name,
      time: `6月${day}日 21:00`,
      tendency: '第3轮',
      meta: '第3轮'
    }
  ]
}
