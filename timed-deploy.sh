#!/bin/bash

# Timed deployment script for AI Bank Details Extractor

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting timed deployment...${NC}"
echo "=============================================="

# Record overall start time
OVERALL_START=$(date +%s)

# Step 1: Clean up
echo -e "${YELLOW}📁 Cleaning up .aws-sam/...${NC}"
CLEANUP_START=$(date +%s)
rm -rf .aws-sam/
CLEANUP_END=$(date +%s)
CLEANUP_TIME=$((CLEANUP_END - CLEANUP_START))
echo -e "${GREEN}✅ Cleanup completed in ${CLEANUP_TIME}s${NC}"
echo ""

# Step 2: Build
echo -e "${YELLOW}🔨 Building with SAM...${NC}"
BUILD_START=$(date +%s)
sam build --use-container
BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))
echo -e "${GREEN}✅ Build completed in ${BUILD_TIME}s${NC}"
echo ""

# Step 3: Deploy
echo -e "${YELLOW}🚀 Deploying to AWS...${NC}"
DEPLOY_START=$(date +%s)
sam deploy --stack-name ai-bank-extractor-dev --region sa-east-1 --no-confirm-changeset --capabilities CAPABILITY_IAM
DEPLOY_END=$(date +%s)
DEPLOY_TIME=$((DEPLOY_END - DEPLOY_START))
echo -e "${GREEN}✅ Deploy completed in ${DEPLOY_TIME}s${NC}"
echo ""

# Calculate total time
OVERALL_END=$(date +%s)
TOTAL_TIME=$((OVERALL_END - OVERALL_START))

# Summary
echo "=============================================="
echo -e "${BLUE}📊 DEPLOYMENT SUMMARY${NC}"
echo "=============================================="
echo -e "Cleanup:  ${CLEANUP_TIME}s"
echo -e "Build:    ${BUILD_TIME}s"
echo -e "Deploy:   ${DEPLOY_TIME}s"
echo "----------------------------------------------"
echo -e "${GREEN}Total:    ${TOTAL_TIME}s ($(($TOTAL_TIME / 60))m $(($TOTAL_TIME % 60))s)${NC}"
echo "=============================================="

# Get API URL
echo -e "${BLUE}🔗 Getting API URLs...${NC}"
API_URL=$(aws cloudformation describe-stacks \
    --stack-name ai-bank-extractor-dev \
    --region sa-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "Could not retrieve API URL")

if [ "$API_URL" != "Could not retrieve API URL" ]; then
    echo -e "${GREEN}🌐 API Gateway URL: ${API_URL}${NC}"
    echo -e "${GREEN}🚀 Application URL: ${API_URL}prod/${NC}"
    echo -e "${GREEN}💚 Health Check: ${API_URL}health${NC}"
else
    echo -e "${RED}❌ Could not retrieve API URL${NC}"
fi

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"