import { Text, View } from '@tarojs/components'

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
        <Text className='ai-report__title'>{title}</Text>
        {status ? <Text className='ai-report__status'>{status}</Text> : null}
      </View>
      {confidence ? <Text className='ai-report__confidence'>{confidence}</Text> : null}
      <Text className='ai-report__text'>{children}</Text>
    </View>
  )
}

