import { motion } from "framer-motion";
import { ChangePasswordForm } from "@/features/auth/components/change-password-form";

export default function ChangePasswordPage() {
  return (
    <motion.div
      className="flex flex-col items-center gap-4 p-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0, 0, 0.2, 1] }}
    >
      <div className="w-full max-w-md">
        <h2 className="mb-4 text-2xl font-semibold font-heading tracking-wide text-primary">
          變更密碼
        </h2>
        <ChangePasswordForm />
      </div>
    </motion.div>
  );
}
