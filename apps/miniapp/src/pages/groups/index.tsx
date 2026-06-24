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
import { goTo, routes } from '@/utils/navigation'

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

function compactBeijingTime(value: string) {
  return value.replace(/^北京时间\s*(\d{1,2})月(\d{1,2})日\s*/, (_match, month, day) => `北京 ${month}/${day} `)
}

export default function GroupsPage() {
  const [activeGroupId, setActiveGroupId] = useState(getRouteGroupId)
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [groupData, setGroupData] = useState<GroupData | null>(null)
  const [keyMatches, setKeyMatches] = useState<HomeData['upcomingMatches']>([])
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const mountedRef = useRef(true)

  const refreshGroupData = useCallback((groupId = activeGroupId) => {
    setLoadState('loading')
    Promise.all([getGroupData(groupId), getHomeData()])
      .then(([data, home]) => {
        if (!mountedRef.current) return
        setGroupData(data)
        const teamNames = new Set(data.teams.map(team => team.name))
        const filtered = home.upcomingMatches.filter(match => teamNames.has(match.home) || teamNames.has(match.away)).slice(0, 2)
        setKeyMatches(filtered)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mountedRef.current) return
        setGroupData(null)
        setKeyMatches([])
        setLoadState('error')
      })
  }, [activeGroupId])

  useEffect(() => {
    mountedRef.current = true
    getGroupList()
      .then(list => {
        if (!mountedRef.current) return
        setGroups(list)
        if (list.length && !list.some(group => group.id === activeGroupId)) {
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

  const displayGroup = useMemo(() => groupData, [groupData])

  const selectGroup = useCallback((group: GroupSummary) => {
    setActiveGroupId(group.id)
    setGroupData(null)
    setKeyMatches([])
  }, [])

  return (
    <View className='page page--groups design-page'>
      <View className='top-bar top-bar--center'>
        <View className='icon-button icon-button--plain' onClick={() => goTo(routes.matches)}>
          <Icon name='back' color='#0f172a' size={34} />
        </View>
        <View className='top-bar__title'>
          <Text className='app-title app-title--sm'>{displayGroup?.title || '小组形势'}</Text>
          <Text className='page-head__subtitle'>{displayGroup?.subtitle || '等待小组数据'}</Text>
          <Text className='page-head__subtitle'>{displayGroup?.updatedAt || '-'}</Text>
        </View>
        <View className='icon-button icon-button--plain' onClick={() => refreshGroupData(activeGroupId)}>
          <Icon name='refresh' color='#0f172a' size={34} />
        </View>
      </View>

      <View className='group-hub'>
        <View className='group-hub__head'>
          <Text className='group-hub__title'>全部小组</Text>
          <Text className='group-hub__meta'>小组赛实时同步</Text>
        </View>
        <View className='group-switcher group-switcher--compact'>
          {groups.length ? groups.map(group => (
            <View
              key={group.id}
              className={`group-switcher__item ${activeGroupId === group.id ? 'group-switcher__item--active' : ''}`}
              onClick={() => selectGroup(group)}
            >
              <Text className='group-switcher__name'>{group.name}</Text>
              <Text className='group-switcher__progress'>{group.matchesFinished}/{group.matchesTotal}</Text>
            </View>
          )) : <View className='empty-state'><Text>暂无小组列表</Text></View>}
        </View>
      </View>

      <View className='group-ai-card group-ai-card--design'>
        <View>
          <View className='group-ai-card__title'>
            <Icon name='spark' color='#2563eb' size={38} />
            <Text>AI 小组判断</Text>
          </View>
          <Text className='group-ai-card__text'>{displayGroup?.summary || '暂无小组判断数据。'}</Text>
        </View>
        <View className='group-ai-card__badge'>
          <Icon name='ai' color='#2563eb' size={54} />
        </View>
      </View>

      <Section title='积分榜' action='完整排名'>
        <View className='table-header table-header--group'>
          <Text>排名</Text>
          <Text>球队</Text>
          <Text>胜 平 负</Text>
          <Text>积分</Text>
          <Text>进 失</Text>
        </View>
        {displayGroup?.teams.length ? displayGroup.teams.map(team => (
          <View
            className='table-row table-row--group'
            key={team.teamId || team.name}
            onClick={() => {
              if (team.teamId) goTo(`${routes.teamDetail}?teamId=${team.teamId}&source=groups&groupId=${activeGroupId}`)
            }}
          >
            <Text className='table-row__rank'>{team.rank}</Text>
            <View className='table-row__team-wrap'>
              <Flag team={team.name} teamId={team.teamId} teamCode={team.teamCode} teamEn={team.nameEn} size='sm' />
              <Text className='table-row__team'>{team.name}</Text>
            </View>
            <Text className='table-row__meta'>{team.record}</Text>
            <Text className='table-row__points'>{team.points}</Text>
            <Text className='table-row__meta'>{team.goals}</Text>
          </View>
        )) : <View className='empty-state'><Text>暂无积分榜数据</Text></View>}
      </Section>

      <Section title='出线概率' action='晋级规则'>
        <View className='qualification-list'>
          {displayGroup?.teams.length ? displayGroup.teams.map(team => (
            <View className='qualification-row' key={team.teamId || team.name}>
              <View className='qualification-row__team'>
                <Flag team={team.name} teamId={team.teamId} teamCode={team.teamCode} teamEn={team.nameEn} size='sm' />
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
          )) : <View className='empty-state'><Text>暂无出线概率数据</Text></View>}
        </View>
      </Section>

      <Section title='关键赛程' action='全部赛程' onAction={() => goTo(routes.matches)}>
        {keyMatches.length ? keyMatches.map(match => (
          <View className='group-match-row' key={match.id} onClick={() => goTo(`${routes.matchDetail}?matchId=${match.id}`)}>
            <View className='group-match-row__team'>
              <Flag team={match.home} teamId={match.homeTeam?.teamId} teamCode={match.homeTeam?.teamCode} teamEn={match.homeTeam?.nameEn} size='sm' />
              <Text>{match.home}</Text>
            </View>
            <Text className='group-match-row__vs'>VS</Text>
            <View className='group-match-row__team group-match-row__team--away'>
              <Text>{match.away}</Text>
              <Flag team={match.away} teamId={match.awayTeam?.teamId} teamCode={match.awayTeam?.teamCode} teamEn={match.awayTeam?.nameEn} size='sm' />
            </View>
            <View className='group-match-row__time'>
              <Text>{match.meta || match.tendency}</Text>
              <Text>{compactBeijingTime(match.time)}</Text>
            </View>
          </View>
        )) : <View className='empty-state'><Text>暂无该小组关键赛程</Text></View>}
        <Text className='section-footnote section-footnote--center'>赛程随官方数据源同步</Text>
      </Section>

      {loadState === 'error' ? <Text className='data-note'>数据连接异常，请稍后重试。</Text> : null}
      <BottomNav active='groups' />
    </View>
  )
}
