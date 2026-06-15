import { Text, View } from '@tarojs/components'
import { Icon } from '@/components/Icon'

type Props = {
  title: string
  status?: string
  confidence?: string
  children: string
}

export function AIReportCard({ title, status, confidence, children }: Props) {
  return (
    <View className='ai-report'>
      <View className='ai-report__head'>
        <View className='ai-report__title-wrap'>
          <View className='ai-report__icon'>
            <Icon name='ai' color='#2563eb' size={34} />
          </View>
          <Text className='ai-report__title'>{title}</Text>
        </View>
        {status ? <Text className='ai-report__status'>{status}</Text> : null}
      </View>
      {confidence ? <Text className='ai-report__confidence'>{confidence}</Text> : null}
      <Text className='ai-report__text'>{children}</Text>
    </View>
  )
}
