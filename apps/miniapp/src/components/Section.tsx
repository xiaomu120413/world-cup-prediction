import { PropsWithChildren } from 'react'
import { Text, View } from '@tarojs/components'

type Props = PropsWithChildren<{
  title: string
  action?: string
}>

export function Section({ title, action, children }: Props) {
  return (
    <View className='section'>
      <View className='section__head'>
        <Text className='section__title'>{title}</Text>
        {action ? <Text className='section__action'>{action}</Text> : null}
      </View>
      <View className='section__body'>{children}</View>
    </View>
  )
}

