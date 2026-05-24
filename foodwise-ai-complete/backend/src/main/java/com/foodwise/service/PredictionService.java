package com.foodwise.service;

import com.foodwise.model.*;
import com.foodwise.repository.PredictionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.csv.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.*;
import org.springframework.http.*;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;
import java.io.*;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class PredictionService {

    private final PredictionRepository predictionRepository;
    private final RestTemplate restTemplate;
    private final SimpMessagingTemplate messagingTemplate;  // WebSocket for notifications

    @Value("${ml.service.url:http://localhost:5001}")
    private String mlServiceUrl;

    public PredictionResponse predict(PredictionRequest req) {
        // Call Python ML service
        Map<String, Object> mlPayload = buildMlPayload(req);
        ResponseEntity<Map> mlResponse;
        try {
            mlResponse = restTemplate.postForEntity(
                mlServiceUrl + "/predict", mlPayload, Map.class);
        } catch (Exception e) {
            log.error("ML service call failed: {}", e.getMessage());
            throw new RuntimeException("ML service unavailable. Please try again.");
        }

        Map<?, ?> mlData = mlResponse.getBody();
        int demand        = (int) mlData.get("demand");
        double wastageProb = (double) mlData.get("wastage_probability");
        int recommended   = (int) mlData.get("recommended_quantity");
        String riskLevel  = (String) mlData.get("waste_risk");

        // Persist to DB
        PredictionRecord record = PredictionRecord.builder()
            .day(req.getDay()).weather(req.getWeather())
            .festival(req.getFestival()).category(req.getCategory())
            .restaurant(req.getRestaurant()).mealType(req.getMealType())
            .previousSales(req.getPreviousSales()).expectedCustomers(req.getExpectedCustomers())
            .predictedDemand(demand).wastageProbability(wastageProb)
            .recommendedQuantity(recommended).riskLevel(riskLevel)
            .createdAt(LocalDateTime.now())
            .build();
        predictionRepository.save(record);

        // Push WebSocket notification if high risk
        if ("High".equals(riskLevel)) {
            WastageAlert alert = new WastageAlert(
                req.getRestaurant(), req.getCategory(), wastageProb,
                "High wastage predicted! Reduce prep by " + (int)(wastageProb * 0.6 * 100) + "%."
            );
            messagingTemplate.convertAndSend("/topic/alerts", alert);
        }

        return PredictionResponse.builder()
            .demand(demand).wastageProbability(wastageProb)
            .recommendedQuantity(recommended).riskLevel(riskLevel)
            .savedKg(estimateSavedKg(demand, recommended))
            .savedCost(estimateSavedCost(demand, recommended, req.getCategory()))
            .build();
    }

    public BulkPredictionResponse bulkPredict(MultipartFile file) {
        List<PredictionRequest> requests = new ArrayList<>();
        try (Reader reader = new InputStreamReader(file.getInputStream());
             CSVParser parser = CSVFormat.DEFAULT.withFirstRecordAsHeader().parse(reader)) {
            for (CSVRecord row : parser) {
                requests.add(PredictionRequest.builder()
                    .day(row.get("day")).weather(row.get("weather"))
                    .festival(row.get("festival")).category(row.get("category"))
                    .restaurant(row.get("restaurant")).mealType(row.get("meal"))
                    .previousSales(Integer.parseInt(row.get("prev_sales").trim()))
                    .expectedCustomers(Integer.parseInt(row.get("customers").trim()))
                    .build());
            }
        } catch (Exception e) {
            throw new RuntimeException("CSV parse error: " + e.getMessage());
        }

        List<PredictionResponse> results = requests.stream().map(this::predict).toList();
        return new BulkPredictionResponse(results, results.size(),
            results.stream().filter(r -> "High".equals(r.getRiskLevel())).count());
    }

    public Page<PredictionRecord> getHistory(Pageable pageable, String restaurant, String riskLevel) {
        if (restaurant != null && riskLevel != null)
            return predictionRepository.findByRestaurantAndRiskLevel(restaurant, riskLevel, pageable);
        if (restaurant != null)
            return predictionRepository.findByRestaurant(restaurant, pageable);
        if (riskLevel != null)
            return predictionRepository.findByRiskLevel(riskLevel, pageable);
        return predictionRepository.findAll(pageable);
    }

    public Map<String, Object> getMlHealth() {
        try {
            ResponseEntity<Map> resp = restTemplate.getForEntity(mlServiceUrl + "/health", Map.class);
            return Objects.requireNonNull(resp.getBody());
        } catch (Exception e) {
            return Map.of("status", "offline", "error", e.getMessage());
        }
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    private Map<String, Object> buildMlPayload(PredictionRequest req) {
        return Map.of(
            "day", req.getDay(), "weather", req.getWeather(),
            "festival", req.getFestival(), "category", req.getCategory(),
            "restaurant", req.getRestaurant(), "meal", req.getMealType(),
            "prev_sales", req.getPreviousSales(), "customers", req.getExpectedCustomers()
        );
    }

    private double estimateSavedKg(int demand, int recommended) {
        return Math.max(0, (demand - recommended) * 0.25); // avg 250g per portion
    }

    private double estimateSavedCost(int demand, int recommended, String category) {
        double costPerPortion = switch (category) {
            case "Proteins" -> 80.0;
            case "Desserts" -> 60.0;
            case "Rice & Grains" -> 25.0;
            default -> 35.0;
        };
        return Math.max(0, (demand - recommended) * costPerPortion);
    }
}
