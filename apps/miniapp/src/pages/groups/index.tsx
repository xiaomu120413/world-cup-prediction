import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getGroupData, type GroupData, type LoadState } from '@/services/data'
import { groupATeams } from '@/services/mock'
import { getTeamIdByName } from '@/services/teamResources'
import { goTo, routes } from '@/utils/navigation'

const fallbackGroup: GroupData = {
  title: '小组形势',
  subtitle: '真实积分榜待同步',
  summary: '连接后端后展示真实积分榜和出线模拟；当前仅显示小组数据待同步空态。',
  teams: groupATeams,
  updatedAt: '更新时间待同步'
}

export default function GroupsPage() {
  const [groupData, setGroupData] = useState<GroupData>(fallbackGroup)
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getGroupData()
      .then(data => {
        if (mounted) {
          setGroupData(data)
          setLoadState('ready')
        }
      })
      .catch(() => {
        if (mounted) {
          setLoadState('error')
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  return (
    <View className='page'>
      <View className='top-bar'>
        <View className='icon-button'>
          <Icon name='back' color='#0f172a' size={32} />
        </View>
        <View className='top-bar__title'>
          <Text className='app-title app-title--sm'>{groupData.title}</Text>
          <Text className='page-head__subtitle'>{groupData.subtitle}</Text>
        </View>
        <View className='icon-button'>
          <Icon name='refresh' color='#2563eb' size={32} />
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新小组形势' detail='稍后显示最新真实积分榜' />}
      {loadState === 'error' && <StatusView title='小组形势暂未更新' detail='仅显示空态占位，请检查小组接口' />}

      <Section title='AI 小组判断'>
        <AIReportCard title='出线形势' status={groupData.updatedAt}>
          {groupData.summary}
        </AIReportCard>
      </Section>

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
                goTo(`${routes.teamDetail}?teamId=${teamId}`)
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

      <Section title='数据状态'>
        <View className='list-row'>
          <View>
            <Text className='list-row__title'>积分榜快照</Text>
            <Text className='list-row__meta'>{groupData.updatedAt}</Text>
          </View>
          <Text className='list-row__right'>{groupData.teams.length ? '真实表' : '待同步'}</Text>
        </View>
        <View className='list-row' onClick={() => goTo(routes.matches)}>
          <View>
            <Text className='list-row__title'>相关赛程</Text>
            <Text className='list-row__meta'>按 matches 表实时同步</Text>
          </View>
          <Text className='list-row__right'>查看</Text>
        </View>
      </Section>

      <BottomNav active='groups' />
    </View>
  )
}
