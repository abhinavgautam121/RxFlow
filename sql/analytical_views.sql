-- PostgreSQL analytical views. UTC storage; date cohorts use Asia/Kolkata.
CREATE OR REPLACE VIEW vw_delivery_base AS
SELECT o.order_id, o.order_created_at, o.order_confirmed_at, o.promised_delivery_at,
       o.promised_service_level, o.fulfillment_center_id, o.zone_id, o.order_status,
       z.city, s.shipment_id, s.delivery_partner_id, s.dispatch_at, s.delivered_at,
       s.shipment_status, s.first_attempt_success, s.delivery_attempt_count, s.shipping_cost,
       (s.shipment_status='DELIVERED' AND s.delivered_at IS NOT NULL AND s.dispatch_at IS NOT NULL
        AND o.promised_delivery_at IS NOT NULL AND o.promised_delivery_at>=o.order_created_at
        AND s.delivered_at>=s.dispatch_at AND s.dispatch_at>=o.order_created_at) AS eligible,
       EXTRACT(EPOCH FROM (s.delivered_at-o.order_created_at))/3600.0 AS delivery_hours
FROM orders o LEFT JOIN shipments s USING(order_id) JOIN zones z USING(zone_id);

CREATE OR REPLACE VIEW vw_daily_delivery_kpis AS
SELECT (order_created_at AT TIME ZONE 'Asia/Kolkata')::date AS order_date,
       COUNT(*) AS total_orders, COUNT(*) FILTER(WHERE eligible) AS eligible_delivered,
       COUNT(*) FILTER(WHERE eligible AND delivered_at<=promised_delivery_at) AS on_time_orders,
       COUNT(*) FILTER(WHERE eligible AND delivered_at>promised_delivery_at) AS late_deliveries,
       AVG(delivery_hours) FILTER(WHERE eligible) AS avg_delivery_hours
FROM vw_delivery_base GROUP BY 1;

CREATE OR REPLACE VIEW vw_partner_performance AS
SELECT delivery_partner_id, COUNT(*) AS total_orders, COUNT(*) FILTER(WHERE eligible) AS delivered,
       100.0*COUNT(*) FILTER(WHERE eligible AND delivered_at<=promised_delivery_at)/NULLIF(COUNT(*) FILTER(WHERE eligible),0) AS on_time_rate,
       AVG(delivery_hours) FILTER(WHERE eligible) AS avg_hours,
       SUM(shipping_cost)/NULLIF(COUNT(*) FILTER(WHERE eligible),0) AS cost_per_successful_delivery
FROM vw_delivery_base GROUP BY 1;

CREATE OR REPLACE VIEW vw_zone_performance AS
SELECT zone_id, city, COUNT(*) AS total_orders, COUNT(*) FILTER(WHERE eligible) AS delivered,
       100.0*COUNT(*) FILTER(WHERE eligible AND delivered_at<=promised_delivery_at)/NULLIF(COUNT(*) FILTER(WHERE eligible),0) AS on_time_rate
FROM vw_delivery_base GROUP BY 1,2;

CREATE OR REPLACE VIEW vw_centre_performance AS
SELECT fulfillment_center_id,COUNT(*) AS total_orders,AVG(delivery_hours) FILTER(WHERE eligible) AS avg_hours,
       COUNT(*) FILTER(WHERE eligible AND delivered_at>promised_delivery_at) AS delayed
FROM vw_delivery_base GROUP BY 1;

-- Snapshot time stays reproducible; replace with transaction_timestamp() for real live data.
CREATE OR REPLACE VIEW vw_inventory_health AS
SELECT sku_id,fulfillment_center_id,SUM(quantity_available) AS on_hand,
       SUM(CASE WHEN expiry_date>(SELECT value::timestamptz FROM dataset_meta WHERE key='as_of')
         AND received_date<=(SELECT value::timestamptz FROM dataset_meta WHERE key='as_of') AND batch_status='ACTIVE'
         THEN GREATEST(0,quantity_available-reserved_quantity-quarantined_quantity) ELSE 0 END) AS sellable_units,
       SUM(quantity_available*unit_cost) AS inventory_value
FROM inventory_batches GROUP BY 1,2;

CREATE OR REPLACE VIEW vw_demand_analysis AS
SELECT (o.order_created_at AT TIME ZONE 'Asia/Kolkata')::date AS demand_date,i.sku_id,o.fulfillment_center_id,
       SUM(i.quantity_ordered) AS demand_units
FROM orders o JOIN order_items i USING(order_id) WHERE o.order_status<>'CANCELLED' GROUP BY 1,2,3;

CREATE OR REPLACE VIEW vw_delay_risk AS
SELECT p.*,s.delivery_partner_id,o.zone_id FROM risk_predictions p JOIN shipments s USING(shipment_id) JOIN orders o USING(order_id);

CREATE OR REPLACE VIEW vw_monthly_trends AS
SELECT date_trunc('month',order_created_at AT TIME ZONE 'Asia/Kolkata')::date AS month,
       COUNT(*) AS total_orders,COUNT(*) FILTER(WHERE eligible) AS delivered,
       COUNT(*) FILTER(WHERE eligible AND delivered_at>promised_delivery_at) AS delayed
FROM vw_delivery_base GROUP BY 1;
