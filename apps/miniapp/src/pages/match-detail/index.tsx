import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
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

export default function MatchDetailPage() {
  const [match, setMatch] = useState<Match>(featuredMatch)
  const [updatedAt, setUpdatedAt] = useState('更新于 18:00')
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getMatchData()
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
  }, [])

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
      {loadState === 'error' && <StatusView title='赛前报告暂未更新' detail='当前显示本地预测快照' />}

      <View className='match-card'>
        <View className='fixture fixture--compact'>
          <View className='fixture__team'>
            <Flag team={match.home} size='lg' />
            <Text className='fixture__name'>{match.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='fixture__time'>{match.time}</Text>
            <Text className='fixture__vs'>VS</Text>
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
        <AIReportCard title='核心判断' status='模型 + 情报'>
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
          <Text className='impact-card__title'>出线影响</Text>
          <ProgressRow label='美国胜后出线概率变化' value={18} meta='+18%' />
          <ProgressRow label='平局后出线概率变化' value={6} meta='+6%' />
          <ProgressRow label='失利后出线概率变化' value={21} meta='-21%' />
        </View>
      </View>

      <BottomNav active='matches' />
    </View>
  )
}
