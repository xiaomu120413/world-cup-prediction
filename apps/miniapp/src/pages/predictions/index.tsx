import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getRankingData, type LoadState } from '@/services/data'
import { championRankings, darkHorseRankings, semiFinalRankings, type RankingTeam } from '@/services/mock'
import { getTeamIdByName } from '@/services/teamResources'
import { goTo, routes } from '@/utils/navigation'

const rankingMap = {
  champion: championRankings,
  semifinal: semiFinalRankings,
  darkhorse: darkHorseRankings
}

const tabLabels = {
  champion: '冠军',
  semifinal: '四强',
  darkhorse: '黑马'
}

type Tab = keyof typeof rankingMap

export default function PredictionsPage() {
  const [active, setActive] = useState<Tab>('champion')
  const [rankings, setRankings] = useState<RankingTeam[]>(rankingMap[active])
  const [rankingMeta, setRankingMeta] = useState({ updatedAt: '更新时间待同步', source: '等待后端真实预测' })
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setRankings(rankingMap[active])
    setLoadState('loading')
    getRankingData(active)
      .then(data => {
        if (mounted) {
          setRankings(data.rankings)
          setRankingMeta({ updatedAt: data.updatedAt, source: data.source })
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
  }, [active])

  return (
    <View className='page'>
      <View className='page-head page-head--center'>
        <Text className='app-title app-title--sm'>预测榜</Text>
        <Text className='page-head__subtitle'>{rankingMeta.source} · {rankingMeta.updatedAt}</Text>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新预测榜' detail='稍后显示最新模拟快照' />}
      {loadState === 'error' && <StatusView title='预测榜暂未更新' detail='仅显示空态占位，请检查 ranking_predictions 接口' />}

      <View className='segmented'>
        {Object.keys(tabLabels).map(key => (
          <Text
            key={key}
            className={`segmented__item ${active === key ? 'segmented__item--active' : ''}`}
            onClick={() => setActive(key as Tab)}
          >
            {tabLabels[key as Tab]}
          </Text>
        ))}
      </View>

      <Section title='AI 榜单解读'>
        <AIReportCard title='概率变化' status={tabLabels[active]}>
          {rankings[0] ? `${rankings[0].name} 暂列${tabLabels[active]}榜首，榜单来自当前 ranking_predictions 快照。原因字段保留模型输出口径，后续可继续接入伤停、天气和赛程路径变化。` : '当前榜单等待模型快照生成。'}
        </AIReportCard>
      </Section>

      <Section title='概率排名'>
        {rankings.length ? rankings.map(team => (
          <View
            className='ranking-row'
            key={team.name}
            onClick={() => goTo(`${routes.teamDetail}?teamId=${team.teamId || getTeamIdByName(team.name)}`)}
          >
            <View className='ranking-row__top'>
              <Text className='ranking-row__rank'>{team.rank}</Text>
              <Flag team={team.name} size='sm' />
              <Text className='ranking-row__name'>{team.name}</Text>
              <Text className='ranking-row__probability'>{team.probability}%</Text>
            </View>
            <View className='ranking-row__detail'>
              <View className='ranking-row__track'>
                <ProgressRow label='' value={team.probability} />
              </View>
              <Text className={team.delta >= 0 ? 'delta delta--up' : 'delta delta--down'}>
                {team.delta >= 0 ? '+' : '-'}{Math.abs(team.delta)}%
              </Text>
              <Text className='reason-chip'>{team.reason}</Text>
            </View>
            {team.meta ? <Text className='ranking-row__meta'>{team.meta}</Text> : null}
          </View>
        )) : <Text className='empty-state'>暂无真实概率排名数据</Text>}
      </Section>

      <View className='today-change-card' onClick={() => goTo(routes.matches)}>
        <View className='today-change-card__icon'>
          <Icon name='chart' color='#2563eb' size={36} />
        </View>
        <View>
          <Text className='today-change-card__title'>今日变化</Text>
          <Text className='today-change-card__text'>{rankings[0] ? `${rankings[0].name} 当前概率 ${rankings[0].probability}%，变化 ${rankings[0].delta >= 0 ? '+' : '-'}${Math.abs(rankings[0].delta)}%。` : '等待最新模型输出。'}</Text>
        </View>
      </View>

      <BottomNav active='predictions' />
    </View>
  )
}
