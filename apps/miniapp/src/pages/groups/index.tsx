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
import { goTo, routes } from '@/utils/navigation'

const fallbackGroup: GroupData = {
  title: 'A组形势',
  subtitle: '小组赛 · 已完成 2/6 场',
  summary: '墨西哥和韩国出线优势明显，捷克仍保留第三名晋级机会。南非需要下一场拿分才能避免提前进入低概率区。',
  teams: groupATeams,
  updatedAt: '模拟更新于 18:00'
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

      {loadState === 'loading' && <StatusView title='正在更新小组形势' detail='稍后显示最新模拟快照' />}
      {loadState === 'error' && <StatusView title='小组形势暂未更新' detail='当前显示本地模拟快照' />}

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
        {groupData.teams.map(team => (
          <View className='table-row' key={team.name} onClick={() => goTo(routes.teamDetail)}>
            <Text className='table-row__rank'>{team.rank}</Text>
            <View className='table-row__team-wrap'>
              <Flag team={team.name} size='sm' />
              <Text className='table-row__team'>{team.name}</Text>
            </View>
            <Text className='table-row__meta'>{team.record}</Text>
            <Text className='table-row__meta'>{team.goals}</Text>
            <Text className='table-row__points'>{team.points}</Text>
          </View>
        ))}
      </Section>

      <Section title='出线概率'>
        <View className='legend-row'>
          <Text className='legend-dot legend-dot--safe'>高概率</Text>
          <Text className='legend-dot legend-dot--warn'>竞争区</Text>
          <Text className='legend-dot legend-dot--danger'>低概率</Text>
        </View>
        {groupData.teams.map(team => (
          <ProgressRow key={team.name} label={team.name} value={team.qualification} />
        ))}
      </Section>

      <Section title='关键赛程'>
        <View className='list-row' onClick={() => goTo(routes.matchDetail)}>
          <View>
            <Text className='list-row__title'>墨西哥 vs 韩国</Text>
            <Text className='list-row__meta'>小组头名战</Text>
          </View>
          <Text className='list-row__right'>决定第一路径</Text>
        </View>
        <View className='list-row' onClick={() => goTo(routes.matchDetail)}>
          <View>
            <Text className='list-row__title'>捷克 vs 南非</Text>
            <Text className='list-row__meta'>第三名关键战</Text>
          </View>
          <Text className='list-row__right'>淘汰风险</Text>
        </View>
      </Section>

      <BottomNav active='groups' />
    </View>
  )
}
