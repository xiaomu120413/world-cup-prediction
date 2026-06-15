import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { EvidenceList } from '@/components/EvidenceList'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { ScorelineDistribution } from '@/components/ScorelineDistribution'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getMatchData, type LoadState } from '@/services/data'
import { featuredMatch, type Match } from '@/services/mock'

function getRouteMatchId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.matchId
  return typeof value === 'string' && value ? value : undefined
}

export default function MatchDetailPage() {
  const [matchId] = useState(getRouteMatchId)
  const [match, setMatch] = useState<Match>(featuredMatch)
  const [updatedAt, setUpdatedAt] = useState('更新于 18:00')
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getMatchData(matchId)
      .then(data => {
        if (mounted) {
          setMatch(data.match)
          setUpdatedAt(data.updatedAt)
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
  }, [matchId])

  return (
    <View className='page'>
      <View className='report-header'>
        <View className='report-header__brand'>
          <View className='report-logo'>
            <Icon name='ai' color='#ffffff' size={34} />
          </View>
          <View>
            <Text className='app-title app-title--sm'>AI 赛前报告</Text>
            <Text className='page-head__subtitle'>{match.status} · {updatedAt}</Text>
          </View>
        </View>
        <View className='icon-button'>
          <Icon name='share' color='#2563eb' size={32} />
        </View>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新赛前报告' detail='稍后显示最新预测快照' />}
      {loadState === 'error' && <StatusView title='赛前报告暂未更新' detail='仅显示空态占位，请检查比赛详情接口' />}

      <View className='match-card'>
        <View className='fixture fixture--compact'>
          <View className='fixture__team'>
            <Flag team={match.home} size='lg' />
            <Text className='fixture__name'>{match.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='fixture__time'>{match.time}</Text>
            <Text className={match.score ? 'fixture__score' : 'fixture__vs'}>{match.score || 'VS'}</Text>
            <Text className='fixture__venue'>{match.venue}</Text>
          </View>
          <View className='fixture__team fixture__team--away'>
            <Flag team={match.away} size='lg' />
            <Text className='fixture__name'>{match.away}</Text>
          </View>
        </View>
      </View>

      <View className='surface probability-card'>
        <View className='surface-head'>
          <Text className='section__title'>胜平负概率</Text>
          <Text className='confidence-pill'>{match.confidence}</Text>
        </View>
        <ProbabilitySummary probabilities={match.probabilities} />
      </View>

      <Section title='AI 分析师结论'>
        <AIReportCard title='核心判断' status={match.modelStatus || '模型 + 情报'}>
          {match.insight}
        </AIReportCard>
      </Section>

      <Section title='关键证据'>
        <EvidenceList items={match.evidence} />
      </Section>

      <Section title='比分分布'>
        <ScorelineDistribution items={match.scorelines} />
      </Section>

      <View className='impact-card'>
        <View className='impact-card__icon'>
          <Icon name='trophy' color='#16a34a' size={36} />
        </View>
        <View className='impact-card__content'>
          <Text className='impact-card__title'>数据状态</Text>
          {match.sourceConfidence !== undefined ? (
            <ProgressRow label='赛程来源可信度' value={match.sourceConfidence} meta={match.source} />
          ) : null}
          <View className='data-point-list'>
            {(match.dataPoints || []).map(item => (
              <View className='data-point-row' key={item.label}>
                <Text className='data-point-row__label'>{item.label}</Text>
                <Text className='data-point-row__value'>{item.value}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      <BottomNav active='matches' />
    </View>
  )
}
