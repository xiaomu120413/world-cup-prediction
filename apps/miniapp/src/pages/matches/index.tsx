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
    <View className='page page--matchday'>
      <View className='matchday-hero' onClick={() => goTo(routes.matchDetail)}>
        <View className='matchday-hero__top'>
          <View>
            <Text className='matchday-hero__eyebrow'>WORLD CUP AI BOARD</Text>
            <Text className='matchday-hero__title'>今日预测</Text>
          </View>
          <Text className='matchday-hero__status'>{featuredMatch.status}</Text>
        </View>

        <View className='matchday-hero__fixture'>
          <View className='team-badge'>
            <Text className='team-badge__abbr'>USA</Text>
            <Text className='team-badge__name'>{featuredMatch.home}</Text>
          </View>
          <View className='matchday-hero__center'>
            <Text className='matchday-hero__time'>{featuredMatch.time}</Text>
            <Text className='matchday-hero__versus'>VS</Text>
            <Text className='matchday-hero__venue'>{featuredMatch.venue}</Text>
          </View>
          <View className='team-badge team-badge--away'>
            <Text className='team-badge__abbr'>PAR</Text>
            <Text className='team-badge__name'>{featuredMatch.away}</Text>
          </View>
        </View>

        <View className='prediction-strip'>
          <Text className='prediction-strip__label'>AI 倾向</Text>
          <Text className='prediction-strip__value'>{featuredMatch.tendency}</Text>
          <Text className='prediction-strip__confidence'>{featuredMatch.confidence}</Text>
        </View>

        <ProbabilitySummary probabilities={featuredMatch.probabilities} />

        <View className='hero-insight'>
          <Text className='hero-insight__label'>赛前信号</Text>
          <Text className='hero-insight__text'>{featuredMatch.insight}</Text>
        </View>
      </View>

      <View className='quick-grid'>
        <View className='quick-card'>
          <Text className='quick-card__value'>50k</Text>
          <Text className='quick-card__label'>模拟次数</Text>
        </View>
        <View className='quick-card'>
          <Text className='quick-card__value'>1.42</Text>
          <Text className='quick-card__label'>美国 xG</Text>
        </View>
        <View className='quick-card'>
          <Text className='quick-card__value'>1-1</Text>
          <Text className='quick-card__label'>最高比分</Text>
        </View>
      </View>

      <Section title='AI 简报'>
        <View onClick={() => goTo(routes.matchDetail)}>
          <AIReportCard title='模型结论' status='可解释预测'>
            美国胜率只领先 15 个百分点，真正的风险在巴拉圭反击效率和低比分平局。
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
              <Text className='list-row__meta'>{match.time} · 小组赛</Text>
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
