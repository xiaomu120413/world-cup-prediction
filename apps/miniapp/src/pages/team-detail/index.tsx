import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { RatingRow } from '@/components/RatingRow'
import { Section } from '@/components/Section'
import { franceProfile } from '@/services/mock'

export default function TeamDetailPage() {
  const team = franceProfile

  return (
    <View className='page'>
      <View className='page-head'>
        <Text className='page-head__title'>{team.name}</Text>
        <Text className='page-head__subtitle'>{team.subtitle}</Text>
        <Text className='muted'>{team.updatedAt}</Text>
      </View>

      <Section title='AI 球队判断'>
        <AIReportCard title='球队状态'>
          {team.summary}
        </AIReportCard>
      </Section>

      <Section title='赛事概率'>
        {team.probabilities.map(item => (
          <View className='list-row' key={item.label}>
            <Text className='list-row__title'>{item.label}</Text>
            <Text className='list-row__right'>{item.value} {item.delta || ''}</Text>
          </View>
        ))}
      </Section>

      <Section title='核心评分'>
        {team.ratings.map(item => (
          <RatingRow key={item.label} label={item.label} value={item.value} />
        ))}
      </Section>

      <Section title='近期状态'>
        <View className='surface'>
          <Text className='list-row__title'>{team.form.headline}</Text>
          {team.form.stats.map(stat => (
            <Text className='muted' key={stat}>{stat}</Text>
          ))}
        </View>
      </Section>

      <Section title='关键球员'>
        {team.players.map(player => (
          <View className='list-row' key={player.name}>
            <View>
              <Text className='list-row__title'>{player.name}</Text>
              <Text className='list-row__meta'>{player.role}</Text>
            </View>
            <Text className='list-row__right'>状态 {player.form}</Text>
          </View>
        ))}
      </Section>

      <Section title='风险提醒'>
        {team.risks.map(risk => (
          <View className='list-row' key={risk.label}>
            <Text className='list-row__title'>{risk.label}</Text>
            <Text className='list-row__right text-negative'>{risk.value}</Text>
          </View>
        ))}
      </Section>

      <BottomNav active='teams' />
    </View>
  )
}
