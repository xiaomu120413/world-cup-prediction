import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { EvidenceList } from '@/components/EvidenceList'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { ScorelineDistribution } from '@/components/ScorelineDistribution'
import { Section } from '@/components/Section'
import { featuredMatch } from '@/services/mock'

export default function MatchDetailPage() {
  return (
    <View className='page'>
      <View className='page-head'>
        <Text className='page-head__title'>AI 赛前报告</Text>
        <Text className='page-head__subtitle'>{featuredMatch.status} · 更新于 18:00</Text>
      </View>

      <View className='surface'>
        <Text className='chip chip--warning'>{featuredMatch.confidence}</Text>
        <Text className='match-title'>{featuredMatch.home} vs {featuredMatch.away}</Text>
        <Text className='match-meta'>{featuredMatch.stage} · {featuredMatch.time} · {featuredMatch.venue}</Text>
        <ProbabilitySummary probabilities={featuredMatch.probabilities} />
      </View>

      <Section title='AI 结论'>
        <AIReportCard title='核心判断' status='模型 + 情报'>
          {featuredMatch.insight}
        </AIReportCard>
      </Section>

      <Section title='关键证据'>
        <EvidenceList items={featuredMatch.evidence} />
      </Section>

      <Section title='比分分布'>
        <ScorelineDistribution items={featuredMatch.scorelines} />
      </Section>

      <Section title='出线影响'>
        <ProgressRow label='美国胜后出线概率变化' value={18} meta='+18%' />
        <ProgressRow label='平局后出线概率变化' value={6} meta='+6%' />
        <ProgressRow label='失利后出线概率变化' value={21} meta='-21%' />
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}

