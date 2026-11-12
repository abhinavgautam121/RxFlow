-- 1. Late deliveries and currently overdue shipments are distinct populations.
SELECT COUNT(*) FILTER (WHERE eligible AND delivered_at>promised_delivery_at) AS delivered_late,
       COUNT(*) FILTER (WHERE shipment_status IN ('PENDING','IN_TRANSIT')
         AND promised_delivery_at>=order_created_at
         AND promised_delivery_at<(SELECT value::timestamptz FROM dataset_meta WHERE key='as_of')) AS currently_overdue
FROM vw_delivery_base;

-- 2. Comparable partner cohorts, rather than a raw speed league table.
SELECT zone_id,promised_service_level,delivery_partner_id,
       COUNT(*) AS delivered,AVG(delivery_hours) AS average_hours,
       AVG((delivered_at<=promised_delivery_at)::int)*100 AS on_time_rate,
       PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delivery_hours) AS p90_hours
FROM vw_delivery_base WHERE eligible GROUP BY 1,2,3 HAVING COUNT(*)>=30;

-- 3. Rolling seven-day zone-level order volume.
WITH daily AS (
  SELECT zone_id,(order_created_at AT TIME ZONE 'Asia/Kolkata')::date AS day,COUNT(*) AS orders
  FROM orders GROUP BY 1,2
)
SELECT *,SUM(orders) OVER (PARTITION BY zone_id ORDER BY day RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW) AS seven_day_orders FROM daily;

-- 4. FEFO only considers eligible stock.
SELECT *,ROW_NUMBER() OVER(PARTITION BY sku_id,fulfillment_center_id ORDER BY expiry_date,batch_id) AS fefo_priority
FROM inventory_batches WHERE batch_status='ACTIVE'
AND expiry_date>(SELECT value::timestamptz FROM dataset_meta WHERE key='as_of')
AND received_date<=(SELECT value::timestamptz FROM dataset_meta WHERE key='as_of')
AND quantity_available-reserved_quantity-quarantined_quantity>0;
