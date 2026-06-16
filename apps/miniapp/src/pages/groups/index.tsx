import { useCallback, useEffect, useRef, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import {
  getGroupData,
  getGroupList,
  getHomeData,
  type GroupData,
  type GroupSummary,
  type HomeData,
  type LoadState
} from '@/services/data'
import { groupATeams } from '@/services/mock'
import { getTeamIdByName } from '@/services/teamResources'
import { goTo, routes } from '@/utils/navigation'

const fallbackGroup: GroupData = {
  id: 'group-a',
  title: '小组形势',
  subtitle: '真实积分榜待同步',
  summary: '连接后端后展示真实积分榜和出线模拟；当前仅显示小组数据待同步空态。',
  teams: groupATeams,
  updatedAt: '更新时间待同步'
}

function getRouteGroupId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.groupId
  return typeof value === 'string' && value ? value : 'group-a'
}

export default function GroupsPage() {
  const [activeGroupId, setActiveGroupId] = useState(getRouteGroupId)
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [groupData, setGroupData] = useState<GroupData>(fallbackGroup)
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
        setKeyMatches(home.upcomingMatches.filter(match => teamNames.has(match.home) || teamNames.has(match.away)).slice(0, 3))
        setLoadState('ready')
      })
      .catch(() => {
        if (!mountedRef.current) return
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

  return (
    <View className='page'>
      <View className='top-bar'>
        <View className='icon-button' onClick={() => goTo(routes.matches)}>
          <Icon name='back' color='#0f172a' size={32} />
        </View>
        <View className='top-bar__title'>
          <Text className='app-title app-title--sm'>{groupData.title}</Text>
          <Text className='page-head__subtitle'>{groupData.subtitle}</Text>
        </View>
        <View className='icon-button' onClick={() => refreshGroupData(activeGroupId)}>
          <Icon name='refresh' color='#2563eb' size={32} />
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新小组形势' detail='稍后显示最新真实积分榜' />}
      {loadState === 'error' && <StatusView title='小组形势暂未更新' detail='仅显示空态占位，请检查小组接口' />}

      <View className='group-switcher'>
        {(groups.length ? groups : [{ id: activeGroupId, name: groupData.title.replace('形势', ''), matchesFinished: groupData.matchesFinished || 0, matchesTotal: groupData.matchesTotal || 6 }]).map(group => (
          <View
            key={group.id}
            className={`group-switcher__item ${activeGroupId === group.id ? 'group-switcher__item--active' : ''}`}
            onClick={() => setActiveGroupId(group.id)}
          >
            <Text className='group-switcher__name'>{group.name}</Text>
            <Text className='group-switcher__meta'>{group.matchesFinished}/{group.matchesTotal}</Text>
          </View>
        ))}
      </View>

      <View className='group-ai-card'>
        <AIReportCard title='AI 小组判断' status={groupData.updatedAt}>
          {groupData.summary}
        </AIReportCard>
      </View>

      <Section title='积分榜'>
        <View className='table-header'>
          <Text>球队</Text>
          <Text>赛果</Text>
          <Text>净胜</Text>
          <Text>积分</Text>
        </View>
        {groupData.teams.length ? groupData.teams.map(team => (
          <View
            className='table-row'
            key={team.name}
            onClick={() => {
              const teamId = team.teamId || getTeamIdByName(team.name)
              if (teamId) {
                goTo(`${routes.teamDetail}?teamId=${teamId}&source=groups&groupId=${activeGroupId}`)
              }
            }}
          >
            <Text className='table-row__rank'>{team.rank}</Text>
            <View className='table-row__team-wrap'>
              <Flag team={team.name} size='sm' />
              <Text className='table-row__team'>{team.name}</Text>
            </View>
            <Text className='table-row__meta'>{team.record}</Text>
            <Text className='table-row__meta'>{team.goals}</Text>
            <Text className='table-row__points'>{team.points}</Text>
          </View>
        )) : <Text className='empty-state'>暂无真实积分榜数据</Text>}
      </Section>

      <Section title='出线概率'>
        <View className='legend-row'>
          <Text className='legend-dot legend-dot--safe'>高概率</Text>
          <Text className='legend-dot legend-dot--warn'>竞争区</Text>
          <Text className='legend-dot legend-dot--danger'>低概率</Text>
        </View>
        {groupData.teams.length ? groupData.teams.map(team => (
          <ProgressRow key={team.name} label={team.name} value={team.qualification} />
        )) : <Text className='empty-state'>暂无真实出线模拟数据</Text>}
      </Section>

      <Section title='关键赛程' action='全部赛程' onAction={() => goTo(routes.matches)}>
        {keyMatches.length ? keyMatches.map(match => (
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
              <Text>{match.meta || '世界杯赛程'}</Text>
              <Text>{match.time}</Text>
            </View>
          </View>
        )) : (
          <View className='list-row list-row--clickable' onClick={() => goTo(routes.matches)}>
            <View>
              <Text className='list-row__title'>查看全部赛程</Text>
              <Text className='list-row__meta'>当前小组赛程待同步</Text>
            </View>
            <Text className='list-row__right'>查看</Text>
          </View>
        )}
      </Section>

      <BottomNav active='groups' />
    </View>
  )
}
