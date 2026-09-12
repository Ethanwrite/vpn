package org.amnezia.awg.xingsui

import android.graphics.Paint
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import org.amnezia.awg.R
import org.amnezia.awg.databinding.XingsuiPlanCardBinding
import org.amnezia.awg.xingsui.model.VipPlan
import java.util.Locale

internal fun membershipMoney(cents: Int): String = String.format(Locale.US, "%.2f", cents / 100.0).trimEnd('0').trimEnd('.')

internal class XingsuiPlanAdapter(private val onClick: (Int) -> Unit) : RecyclerView.Adapter<XingsuiPlanAdapter.Holder>() {
    var plans: List<VipPlan> = emptyList()
    var selectedIndex = 0
    var geometry: XingsuiCarouselGeometry? = null
    class Holder(val binding: XingsuiPlanCardBinding) : RecyclerView.ViewHolder(binding.root)
    override fun getItemCount() = plans.size
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = Holder(XingsuiPlanCardBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    override fun onBindViewHolder(holder: Holder, position: Int) {
        val plan = plans[position]
        val b = holder.binding
        val ctx = b.root.context
        geometry?.let { g ->
            b.root.layoutParams = RecyclerView.LayoutParams(g.cardWidth, ViewGroup.LayoutParams.MATCH_PARENT).apply {
                leftMargin = g.cardMargin; rightMargin = g.cardMargin
            }
        }
        b.root.clipToOutline = true
        b.planIndex.text = String.format(Locale.US, "%02d / 会员计划", position + 1)
        b.planName.text = plan.name
        b.planPrice.text = "¥" + membershipMoney(plan.salePriceCents)
        b.planPeriod.text = "${plan.durationDays} 天 · 相当于 ¥${String.format(Locale.US, "%.2f", plan.salePriceCents / 100.0 / plan.durationDays.coerceAtLeast(1))} / 天"
        b.planOriginal.visibility = if (plan.originalPriceCents > plan.salePriceCents) View.VISIBLE else View.INVISIBLE
        b.planOriginal.text = "原价 ¥" + membershipMoney(plan.originalPriceCents)
        b.planOriginal.paintFlags = b.planOriginal.paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
        val selected = position == selectedIndex
        b.root.strokeColor = ctx.getColor(if (selected) R.color.xingsui_red else R.color.xingsui_line)
        b.planSelection.text = if (selected) "●  当前选择" else "选择此计划  ›"
        b.planSelection.setTextColor(ctx.getColor(if (selected) R.color.xingsui_red else R.color.xingsui_muted))
        b.root.isSelected = selected
        b.root.contentDescription = "${plan.name}，${plan.durationDays} 天，${b.planPrice.text}，${b.planSelection.text}"
        b.root.setOnClickListener { holder.adapterPosition.takeIf { it != RecyclerView.NO_POSITION }?.let(onClick) }
    }
    fun select(index: Int) {
        if (index == selectedIndex) return
        val old = selectedIndex
        selectedIndex = index
        notifyItemChanged(old)
        notifyItemChanged(index)
    }
}
