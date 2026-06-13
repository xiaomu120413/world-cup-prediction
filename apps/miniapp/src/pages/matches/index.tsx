import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { championTop, featuredMatch, upcomingMatches } from '@/services/mock'
import { goTo, routes } from '@/utils/navigation'

export default function MatchesPage() {
  return (
    <View className='page'>
      <View className='page-head'>
        <Text className='page-head__title'>世界杯预测</Text>
        <Text className='page-head__subtitle'>今日赛程 · 6月13日</Text>
        <Text className='muted'>数据更新于 18:00</Text>
      </View>

      <Section title='今日重点'>
        <View className='surface' onClick={() => goTo(routes.matchDetail)}>
          <Text className='chip'>{featuredMatch.status}</Text>
          <Text className='match-title'>{featuredMatch.home} vs {featuredMatch.away}</Text>
          <Text className='match-meta'>{featuredMatch.tendency} · {featuredMatch.confidence}</Text>
          <ProbabilitySummary probabilities={featuredMatch.probabilities} />
          <AIReportCard title='AI 赛前情报'>
            美国整体略占优，但小比分概率较高。
          </AIReportCard>
          <View className='primary-link'>
            <Text>查看 AI 赛前报告</Text>
          </View>
        </View>
      </Section>

      <Section title='即将开始'>
        {upcomingMatches.map(match => (
          <View className='list-row' key={match.id} onClick={() => goTo(routes.matchDetail)}>
            <View>
              <Text className='list-row__title'>{match.home} vs {match.away}</Text>
              <Text className='list-row__meta'>{match.time}</Text>
            </View>
            <Text className='list-row__right'>{match.tendency}</Text>
          </View>
        ))}
      </Section>

      <Section title='冠军概率' action='查看全部'>
        {championTop.map(team => (
          <ProgressRow key={team.name} label={team.name} value={team.probability} />
        ))}
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}

