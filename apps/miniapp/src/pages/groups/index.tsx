import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { Section } from '@/components/Section'
import {
  getGroupData,
  getGroupList,
  getHomeData,
  type GroupData,
  type GroupSummary,
  type HomeData,
  type LoadState
} from '@/services/data'
import { getTeamIdByName } from '@/services/teamResources'
import {
  getFallbackGroupData,
  getFallbackGroupMatches,
  getFallbackGroupSummaries
} from '@/services/tournamentStructure'
import { goTo, routes } from '@/utils/navigation'

const fallbackGroup = getFallbackGroupData()
const fallbackMatches = getFallbackGroupMatches()

function getRouteGroupId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.groupId
  return typeof value === 'string' && value ? value : 'group-a'
}

function qualificationTone(value: number) {
  if (value >= 75) return 'safe'
  if (value >= 45) return 'warn'
  return 'danger'
}

export default function GroupsPage() {
  const [activeGroupId, setActiveGroupId] = useState(getRouteGroupId)
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [groupData, setGroupData] = useState<GroupData>(fallbackGroup)
  const [keyMatches, setKeyMatches] = useState<HomeData['upcomingMatches']>(fallbackMatches)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const mountedRef = useRef(true)

  const refreshGroupData = useCallback((groupId = activeGroupId) => {
    const fallbackForGroup = getFallbackGroupData(groupId)
    const fallbackMatchesForGroup = getFallbackGroupMatches(groupId)
    setLoadState('loading')
    Promise.all([getGroupData(groupId), getHomeData()])
      .then(([data, home]) => {
        if (!mountedRef.current) return
        const resolvedGroup = data.teams.length && !data.summary.includes('待同步') ? data : fallbackForGroup
        setGroupData(resolvedGroup)
        const teamNames = new Set(resolvedGroup.teams.map(team => team.name))
        const filtered = home.upcomingMatches.filter(match => teamNames.has(match.home) || teamNames.has(match.away)).slice(0, 2)
        setKeyMatches(filtered.length ? filtered : fallbackMatchesForGroup)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mountedRef.current) return
        setGroupData(fallbackForGroup)
        setKeyMatches(fallbackMatchesForGroup)
        setLoadState('error')
      })
  }, [activeGroupId])

  useEffect(() => {
    mountedRef.current = true
    getGroupList()
      .then(list => {
        if (!mountedRef.current) return
        setGroups(list)
        if (list.length && !list.some(group => group.id === activeGroupId) && !getFallbackGroupSummaries().some(group => group.id === activeGroupId)) {
          setActiveGroupId(list[0].id)
        }
      })
      .catch(() => {
        if (mountedRef.current) setGroups([])
      })

    return () => {
      mountedRef.current = false
    }
  }, [activeGroupId])

  useEffect(() => {
    refreshGroupData(activeGroupId)
  }, [activeGroupId, refreshGroupData])

  const displayGroup = useMemo(() => {
    const fallbackForGroup = getFallbackGroupData(activeGroupId)
    const completed = groupData.matchesFinished ?? fallbackForGroup.matchesFinished ?? 2
    const total = groupData.matchesTotal ?? fallbackForGroup.matchesTotal ?? 6
    return {
      ...groupData,
      teams: groupData.teams.length ? groupData.teams : fallbackForGroup.teams,
      subtitle: `小组赛 · 已完成 ${completed}/${total} 场`,
      updatedAt: groupData.updatedAt && !groupData.updatedAt.includes('待') ? groupData.updatedAt : fallbackForGroup.updatedAt,
      summary: groupData.summary && !groupData.summary.includes('待') ? groupData.summary : fallbackForGroup.summary
    }
  }, [activeGroupId, groupData])

  const groupOptions = useMemo(() => {
    const merged = new Map(getFallbackGroupSummaries().map(group => [group.id, group]))
    groups.forEach(group => {
      const fallback = merged.get(group.id)
      merged.set(group.id, fallback ? { ...fallback, ...group } : group)
    })
    return getFallbackGroupSummaries().map(group => merged.get(group.id) || group)
  }, [groups])

  const selectGroup = useCallback((group: GroupSummary) => {
    setActiveGroupId(group.id)
    setGroupData(getFallbackGroupData(group.id))
    setKeyMatches(getFallbackGroupMatches(group.id))
  }, [])

  return (
    <View className='page page--groups design-page'>
      <View className='top-bar top-bar--center'>
        <View className='icon-button icon-button--plain' onClick={() => goTo(routes.matches)}>
          <Icon name='back' color='#0f172a' size={34} />
        </View>
        <View className='top-bar__title'>
          <Text className='app-title app-title--sm'>{displayGroup.title}</Text>
          <Text className='page-head__subtitle'>{displayGroup.subtitle}</Text>
          <Text className='page-head__subtitle'>{displayGroup.updatedAt}</Text>
        </View>
        <View className='icon-button icon-button--plain' onClick={() => refreshGroupData(activeGroupId)}>
          <Icon name='refresh' color='#0f172a' size={34} />
        </View>
      </View>

      <View className='group-hub'>
        <View className='group-hub__head'>
          <Text className='group-hub__title'>全部小组</Text>
          <Text className='group-hub__meta'>点击查看具体小组形势</Text>
        </View>
        <View className='group-switcher group-switcher--compact'>
          {groupOptions.map(group => (
            <View
              key={group.id}
              className={`group-switcher__item ${activeGroupId === group.id ? 'group-switcher__item--active' : ''}`}
              onClick={() => selectGroup(group)}
            >
              <Text className='group-switcher__name'>{group.name}</Text>
              <Text className='group-switcher__progress'>{group.matchesFinished}/{group.matchesTotal}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='group-ai-card group-ai-card--design'>
        <View>
          <View className='group-ai-card__title'>
            <Icon name='spark' color='#2563eb' size={38} />
            <Text>AI 小组判断</Text>
          </View>
          <Text className='group-ai-card__text'>{displayGroup.summary}</Text>
        </View>
        <View className='group-ai-card__badge'>
          <Icon name='ai' color='#2563eb' size={54} />
        </View>
      </View>

      <Section title='积分榜' action='完整排名'>
        <View className='table-header table-header--group'>
          <Text>排名</Text>
          <Text>球队</Text>
          <Text>胜/平/负</Text>
          <Text>积分</Text>
          <Text>进/失</Text>
        </View>
        {displayGroup.teams.map(team => (
          <View
            className='table-row table-row--group'
            key={team.name}
            onClick={() => {
              const teamId = team.teamId || getTeamIdByName(team.name)
              if (teamId) goTo(`${routes.teamDetail}?teamId=${teamId}&source=groups&groupId=${activeGroupId}`)
            }}
          >
            <Text className='table-row__rank'>{team.rank}</Text>
            <View className='table-row__team-wrap'>
              <Flag team={team.name} size='sm' />
              <Text className='table-row__team'>{team.name}</Text>
            </View>
            <Text className='table-row__meta'>{team.record}</Text>
            <Text className='table-row__points'>{team.points}</Text>
            <Text className='table-row__meta'>{team.goals}</Text>
          </View>
        ))}
      </Section>

      <Section title='出线概率' action='晋级规则'>
        <View className='qualification-list'>
          {displayGroup.teams.map(team => (
            <View className='qualification-row' key={team.name}>
              <View className='qualification-row__team'>
                <Flag team={team.name} size='sm' />
                <Text>{team.name}</Text>
              </View>
              <View className='qualification-row__track'>
                <View
                  className={`qualification-row__bar qualification-row__bar--${qualificationTone(team.qualification)}`}
                  style={{ width: `${Math.max(0, Math.min(100, team.qualification))}%` }}
                />
              </View>
              <Text className={`qualification-row__value qualification-row__value--${qualificationTone(team.qualification)}`}>{team.qualification}%</Text>
            </View>
          ))}
        </View>
        <View className='legend-row legend-row--design'>
          <Text className='legend-dot legend-dot--safe'>优势显著</Text>
          <Text className='legend-dot legend-dot--warn'>形势胶着</Text>
          <Text className='legend-dot legend-dot--danger'>出线困难</Text>
          <Text className='legend-dot legend-dot--muted'>基本无望</Text>
        </View>
      </Section>

      <Section title='关键赛程' action='全部赛程' onAction={() => goTo(routes.matches)}>
        {(keyMatches.length ? keyMatches : fallbackMatches).map(match => (
          <View className='group-match-row' key={match.id} onClick={() => goTo(`${routes.matchDetail}?matchId=${match.id}`)}>
            <View className='group-match-row__team'>
              <Flag team={match.home} size='sm' />
              <Text>{match.home}</Text>
            </View>
            <Text className='group-match-row__vs'>VS</Text>
            <View className='group-match-row__team group-match-row__team--away'>
              <Text>{match.away}</Text>
              <Flag team={match.away} size='sm' />
            </View>
            <View className='group-match-row__time'>
              <Text>{match.meta || match.tendency || '第3轮'}</Text>
              <Text>{match.time}</Text>
            </View>
          </View>
        ))}
        <Text className='section-footnote section-footnote--center'>赛程时间均为当地时间</Text>
      </Section>

      {loadState === 'error' ? <Text className='data-note'>后端未连接，当前使用设计稿样例数据。</Text> : null}
      <BottomNav active='groups' />
    </View>
  )
}
